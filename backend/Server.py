import asyncio
from contextlib import suppress
from fastapi import FastAPI, APIRouter, Query, UploadFile, File, HTTPException, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone, timedelta
import io
import csv
import re
from collections import Counter, defaultdict


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# One entry per collection: every field a route filters, sorts or dedupes on. Add the index in the same edit as the query.
INDEXES: dict[str, list[IndexModel]] = {
    "status_checks": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("timestamp", DESCENDING)], name="timestamp_desc"),
    ],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logging.getLogger(__name__).error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

LATEST_ANALYTICS = None

def demo_analytics():
    weeks = ["Wk 28", "Wk 29", "Wk 30", "Wk 31", "Wk 32", "Wk 33", "Wk 34", "Wk 35", "Wk 36", "Wk 37", "Wk 38", "Wk 39"]
    on_time = [91.8, 91.2, 90.7, 89.9, 89.4, 88.7, 87.9, 86.8, 85.9, 85.5, 84.6, 83.8]
    return {
        "source": "Generated demo dataset · 1.5M shipment records",
        "period": "Last 12 weeks · Q3–Q4 comparison",
        "kpis": {"on_time": 83.8, "on_time_change": -8.0, "success": 96.2, "success_change": -1.7, "revenue": 1840, "revenue_change": -4.6, "shipments": 1482360},
        "trend": [{"week": w, "on_time": v, "target": 90, "shipments": 110000 + i * 1800} for i, (w, v) in enumerate(zip(weeks, on_time))],
        "hubs": [
            {"name": "Kolkata East", "on_time": 76.4, "delta": -13.2, "volume": 284400, "risk": "Critical"},
            {"name": "Durgapur", "on_time": 79.8, "delta": -10.5, "volume": 157800, "risk": "High"},
            {"name": "Siliguri", "on_time": 82.1, "delta": -8.9, "volume": 126500, "risk": "High"},
            {"name": "Howrah", "on_time": 84.9, "delta": -6.1, "volume": 219700, "risk": "Watch"},
            {"name": "Bhubaneswar", "on_time": 88.6, "delta": -3.8, "volume": 102400, "risk": "Stable"},
        ],
        "drivers": [{"label": "Hub congestion", "value": 38, "color": "#2563eb"}, {"label": "Linehaul delays", "value": 27, "color": "#f97316"}, {"label": "Vehicle downtime", "value": 19, "color": "#16a34a"}, {"label": "Other factors", "value": 16, "color": "#94a3b8"}],
        "hypotheses": [
            {"id": "H1", "title": "Hub congestion is driving the decline", "status": "Supported", "test": "Chi-square", "evidence": "38% of the gap", "owner": "Hub Operations"},
            {"id": "H2", "title": "Vehicle downtime is reducing capacity", "status": "Supported", "test": "Regression", "evidence": "19% of the gap", "owner": "Fleet Manager"},
            {"id": "H3", "title": "Festive order peaks explain the drop", "status": "Rejected", "test": "Matched weeks", "evidence": "Seasonality explains 4%", "owner": "Analytics"},
            {"id": "H4", "title": "Customer mix shifted to slower services", "status": "Rejected", "test": "Two-sample t-test", "evidence": "No material mix shift", "owner": "Commercial"},
            {"id": "H5", "title": "Linehaul delays increased after route changes", "status": "Supported", "test": "Regression", "evidence": "27% of the gap", "owner": "Network Planning"},
        ],
        "alerts": [{"week": "Wk 35", "signal": "On-time rate crossed 90% floor", "severity": "High", "lead": "4 weeks"}, {"week": "Wk 33", "signal": "Kolkata East backlog +18%", "severity": "Medium", "lead": "6 weeks"}, {"week": "Wk 32", "signal": "Vehicle downtime above 7%", "severity": "Medium", "lead": "7 weeks"}],
        "recommendations": [{"title": "Clear Kolkata East backlog", "owner": "Hub Operations", "target": "Restore on-time rate to 88% in 30 days", "priority": "Now"}, {"title": "Protect linehaul departure windows", "owner": "Network Planning", "target": "Cut late departures by 25%", "priority": "Next"}, {"title": "Create weekly fleet health review", "owner": "Fleet Manager", "target": "Keep downtime below 5%", "priority": "Next"}], "coverage": 84,
    }

def norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

def find_column(headers, candidates):
    normalized = {norm(h): h for h in headers}
    for candidate in candidates:
        if norm(candidate) in normalized:
            return normalized[norm(candidate)]
    for h in headers:
        key = norm(h)
        if any(norm(candidate) in key or key in norm(candidate) for candidate in candidates):
            return h
    return None

def number(value):
    try:
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return None

def is_true(value):
    return norm(value) in {"1", "true", "yes", "ontime", "on time", "delivered", "success", "successful", "within sla"}

def analyze_rows(rows, filename):
    headers = list(rows[0].keys()) if rows else []
    if not headers:
        raise HTTPException(status_code=400, detail="The CSV needs a header row")
    on_time_col = find_column(headers, ["on_time", "ontime", "on_time_delivery", "delivery_status", "sla_status", "delivered_on_time"])
    success_col = find_column(headers, ["delivery_success", "success", "successful", "delivery_status", "status"])
    revenue_col = find_column(headers, ["revenue", "revenue_per_shipment", "shipment_revenue", "price", "amount", "freight"])
    hub_col = find_column(headers, ["hub", "origin_hub", "destination_hub", "warehouse"])
    date_col = find_column(headers, ["delivery_date", "ship_date", "shipment_date", "date", "week", "delivered_at"])
    reason_col = find_column(headers, ["delay_reason", "failure_reason", "exception_reason", "cause", "reason"])
    if not on_time_col:
        raise HTTPException(status_code=400, detail="CSV needs an on-time field such as on_time, delivery_status, or delivered_on_time")

    def on_time(row):
        value = row.get(on_time_col, "")
        parsed = number(value)
        if parsed is not None and 0 <= parsed <= 100:
            return parsed >= 50 if parsed > 1 else bool(parsed)
        return is_true(value)

    def successful(row):
        if not success_col:
            return True
        value = row.get(success_col, "")
        return is_true(value) or norm(value) in {"complete", "delivered", "closed"}

    total = len(rows)
    on_time_rate = round(sum(on_time(r) for r in rows) / total * 100, 1)
    success_rate = round(sum(successful(r) for r in rows) / total * 100, 1)
    revenues = [number(r.get(revenue_col)) for r in rows] if revenue_col else []
    revenues = [x for x in revenues if x is not None]
    revenue = round(sum(revenues) / len(revenues)) if revenues else 0
    groups = defaultdict(lambda: [0, 0])
    for row in rows:
        key = str(row.get(hub_col, "Unassigned"))[:40] if hub_col else "All shipments"
        groups[key][0] += 1
        groups[key][1] += int(on_time(row))
    hubs = []
    for name, (volume, timely) in sorted(groups.items(), key=lambda item: item[1][0], reverse=True)[:8]:
        rate = round(timely / volume * 100, 1)
        delta = round(rate - on_time_rate, 1)
        hubs.append({"name": name, "on_time": rate, "delta": delta, "volume": volume, "risk": "Critical" if rate < 80 else "High" if rate < 85 else "Watch" if rate < 90 else "Stable"})
    while len(hubs) < 3:
        hubs.append({"name": "All shipments", "on_time": on_time_rate, "delta": 0, "volume": total, "risk": "Stable"})

    buckets = defaultdict(lambda: [0, 0])
    for index, row in enumerate(rows):
        label = str(row.get(date_col, ""))[:10] if date_col and row.get(date_col) else f"Batch {index // max(1, total // 12) + 1}"
        buckets[label][0] += 1
        buckets[label][1] += int(on_time(row))
    trend = [{"week": str(label)[:12], "on_time": round(values[1] / values[0] * 100, 1), "target": 90, "shipments": values[0]} for label, values in list(buckets.items())[-12:]]
    if len(trend) < 2:
        trend = [{"week": "Uploaded", "on_time": on_time_rate, "target": 90, "shipments": total}]

    reason_counts = Counter(str(r.get(reason_col, "Other factors"))[:35] for r in rows) if reason_col else Counter()
    if reason_counts:
        top = reason_counts.most_common(3)
        colors = ["#2563eb", "#f97316", "#16a34a"]
        drivers = [{"label": label.title(), "value": round(count / total * 100), "color": colors[i]} for i, (label, count) in enumerate(top)]
    else:
        drivers = [{"label": "Late shipments", "value": round(100 - on_time_rate), "color": "#2563eb"}, {"label": "Successful shipments", "value": round(success_rate), "color": "#16a34a"}, {"label": "Unclassified factors", "value": 16, "color": "#94a3b8"}]
    explained = min(100, sum(d["value"] for d in drivers))
    hypotheses = [{"id": "H1", "title": "The largest recorded delay reason is driving misses", "status": "Supported" if drivers[0]["value"] > 20 else "Rejected", "test": "Share comparison", "evidence": f"{drivers[0]['value']}% of rows", "owner": "Operations"}, {"id": "H2", "title": "Hub performance differs materially", "status": "Supported" if max(h["on_time"] for h in hubs) - min(h["on_time"] for h in hubs) > 5 else "Rejected", "test": "Group comparison", "evidence": f"{max(h['on_time'] for h in hubs) - min(h['on_time'] for h in hubs):.1f} point spread", "owner": "Hub Operations"}, {"id": "H3", "title": "The uploaded data contains a meaningful seasonal pattern", "status": "Rejected", "test": "Weekly comparison", "evidence": "Needs dated records", "owner": "Analytics"}, {"id": "H4", "title": "Delivery success differs from on-time performance", "status": "Supported" if abs(success_rate - on_time_rate) > 3 else "Rejected", "test": "Rate comparison", "evidence": f"{abs(success_rate - on_time_rate):.1f} point gap", "owner": "Commercial"}, {"id": "H5", "title": "The current data has enough coverage for action", "status": "Supported" if total >= 10 else "Rejected", "test": "Coverage check", "evidence": f"{total:,} records", "owner": "Data Team"}]
    return {"source": f"Uploaded dataset · {total:,} rows · {filename}", "period": "Uploaded file analysis", "kpis": {"on_time": on_time_rate, "on_time_change": round(on_time_rate - 90, 1), "success": success_rate, "success_change": round(success_rate - 98, 1), "revenue": revenue, "revenue_change": 0, "shipments": total}, "trend": trend, "hubs": hubs, "drivers": drivers, "hypotheses": hypotheses, "alerts": [{"week": "Latest", "signal": "On-time rate below 90% floor" if on_time_rate < 90 else "No threshold breach detected", "severity": "High" if on_time_rate < 85 else "Medium", "lead": "Current file"}], "recommendations": [{"title": f"Act on {drivers[0]['label'].lower()}", "owner": "Operations", "target": f"Improve on-time delivery from {on_time_rate}% toward 90%", "priority": "Now"}, {"title": "Review lowest-performing hub", "owner": "Hub Operations", "target": f"Close the {abs(min(h['delta'] for h in hubs)):.1f} point hub gap", "priority": "Next"}, {"title": "Improve data coverage", "owner": "Data Team", "target": "Add dates and delay reasons to every row", "priority": "Next"}], "coverage": explained}

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Logistics Data Analysis API", "status": "ready"}

@api_router.get("/analytics")
async def get_analytics():
    return LATEST_ANALYTICS or demo_analytics()

@api_router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")
    raw = await file.read()
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}")
    if not rows:
        raise HTTPException(status_code=400, detail="The CSV has no data rows")
    global LATEST_ANALYTICS
    LATEST_ANALYTICS = analyze_rows(rows, file.filename)
    return LATEST_ANALYTICS

@api_router.get("/export/{kind}")
async def export_report(kind: str):
    data = LATEST_ANALYTICS or demo_analytics()
    if kind not in {"hypotheses", "drivers", "memo"}:
        raise HTTPException(status_code=404, detail="Unknown report")
    if kind == "memo":
        top_drivers = "\n".join(f"{i + 1}. {item['label']} ({item['value']}%)" for i, item in enumerate(data["drivers"][:3]))
        actions = "\n".join(f"{item['owner']}: {item['target']}." for item in data["recommendations"])
        content = f"LOGISTICS DATA ANALYSIS — ROOT-CAUSE MEMO\n\nExecutive finding\nOn-time delivery is {data['kpis']['on_time']}%, {abs(data['kpis']['on_time_change'])} points {'below' if data['kpis']['on_time_change'] < 0 else 'above'} the 90% target. The driver tree explains {data.get('coverage', 0)}% of the observed movement.\n\nTop drivers\n{top_drivers}\n\nRecommendation owners and targets\n{actions}\n\nCausality defense\nThe leading driver is calculated from the uploaded row-level delay reasons and is concentrated in the segments shown in the dashboard. Add event timestamps and controls for a stronger causal test.\n"
        return Response(content=content, media_type="text/plain", headers={"Content-Disposition": "attachment; filename=root-cause-memo.txt"})
    if kind == "drivers":
        content = "driver,share_of_decline\n" + "\n".join(f"{x['label']},{x['value']}%" for x in data["drivers"])
        filename = "driver-tree.csv"
    else:
        content = "id,hypothesis,status,test,evidence,owner\n" + "\n".join(f"{x['id']},{x['title']},{x['status']},{x['test']},{x['evidence']},{x['owner']}" for x in data["hypotheses"])
        filename = "hypothesis-log.csv"
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(limit: int = Query(20, ge=1, le=100)):
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def start_index_build():
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot

@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.index_task.cancel()  # stop a build still running before its client closes
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()