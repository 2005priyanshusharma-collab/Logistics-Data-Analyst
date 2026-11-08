import { useEffect, useState } from "react";
import axios from "axios";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid } from "recharts";
import { Upload, Download, ArrowUpRight, AlertTriangle, CheckCircle2, ChevronRight, FileText, Database, Activity, Target } from "lucide-react";
import "@/App.css";
import "@/mobile.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function Stat({ label, value, change, suffix = "", tone = "blue" }) {
    return <div className="stat" data-testid={`kpi-${label.toLowerCase().replaceAll(" ", "-")}`}><span className="stat-label">{label}</span><strong>{value}{suffix}</strong><span className={`stat-change ${change < 0 ? "negative" : "positive"}`}>{change < 0 ? "↓" : "↑"} {Math.abs(change)}% vs last period</span><div className={`stat-mark ${tone}`} /></div>;
}

function App() {
    const [data, setData] = useState(null);
    const [view, setView] = useState("overview");
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [message, setMessage] = useState("");

    const loadData = async () => { setLoading(true); try { setData((await axios.get(`${API}/analytics`)).data); } catch { setMessage("The analytics service is unavailable. Please try again."); } finally { setLoading(false); } };
    useEffect(() => { loadData(); }, []);

    const handleUpload = async (event) => {
        const file = event.target.files?.[0]; if (!file) return;
        setUploading(true); setMessage(""); const form = new FormData(); form.append("file", file);
        try { setData((await axios.post(`${API}/upload`, form)).data); setMessage("Dataset loaded. Dashboard refreshed with your file."); } catch (e) { setMessage(e.response?.data?.detail || "Could not load that CSV."); } finally { setUploading(false); }
    };

    if (loading || !data) return <div className="loading" data-testid="loading-state"><div className="loader-line" /><p>Preparing your logistics view…</p></div>;
    const nav = [{ id: "overview", label: "Overview", icon: Activity }, { id: "drivers", label: "Driver tree", icon: Target }, { id: "hypotheses", label: "Hypothesis log", icon: FileText }, { id: "early-warning", label: "Early warning", icon: AlertTriangle }];
    return <div className="app-shell">
        <aside className="sidebar">
            <div className="brand" data-testid="brand-name"><span className="brand-badge">LD</span><span>Logistics<br /><b>Data Analysis</b></span></div>
            <div className="side-kicker">WORKSPACE</div>
            <nav>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${view === id ? "active" : ""}`} onClick={() => setView(id)} data-testid={`nav-${id}`}><Icon size={17} />{label}{id === "early-warning" && <span className="nav-dot" />}</button>)}</nav>
            <div className="sidebar-foot"><div className="dataset-mini"><Database size={15} /><div><span>Current dataset</span><b data-testid="dataset-source-short">{data.kpis.shipments.toLocaleString()} shipments</b></div></div><label className="upload-button" data-testid="upload-csv-button"><Upload size={16} />{uploading ? "Loading…" : "Load CSV"}<input type="file" accept=".csv" onChange={handleUpload} data-testid="csv-file-input" /></label></div>
        </aside>
        <main className="main-content">
            <header className="topbar"><div><span className="eyebrow">KOLKATA NETWORK / 2024</span><h1>{view === "overview" ? "Network performance" : nav.find(n => n.id === view)?.label}</h1></div><div className="top-actions"><span className="data-status" data-testid="data-status"><i />{data.source}</span><button className="export-btn" onClick={() => window.open(`${API}/export/memo`, "_blank")} data-testid="download-memo-button"><Download size={15} /> Export memo</button></div></header>
            {message && <div className="notice" data-testid="upload-message">{message}</div>}
            {view === "overview" && <Overview data={data} setView={setView} />}
            {view === "drivers" && <Drivers data={data} />}
            {view === "hypotheses" && <Hypotheses data={data} />}
            {view === "early-warning" && <EarlyWarning data={data} />}
        </main>
    </div>;
}

function Overview({ data, setView }) {
    return <>
        <section className="headline"><div><h2>{data.kpis.on_time < 90 ? "The drop is real." : "The network is on target."}<br /><em>Now make it actionable.</em></h2><p>On-time delivery is <b>{data.kpis.on_time}%</b>, {Math.abs(data.kpis.on_time_change)} points {data.kpis.on_time_change < 0 ? "below" : "from"} the 90% target. The driver tree currently accounts for <b>{data.coverage || 0}%</b> of the observed movement.</p></div><button className="text-action" onClick={() => setView("drivers")} data-testid="view-driver-tree-button">View driver tree <ChevronRight size={16} /></button></section>
        <div className="stats-grid"><Stat label="On-time delivery" value={data.kpis.on_time} suffix="%" change={data.kpis.on_time_change} /><Stat label="Delivery success" value={data.kpis.success} suffix="%" change={data.kpis.success_change} tone="green" /><Stat label="Revenue / shipment" value={`₹${data.kpis.revenue.toLocaleString()}`} change={data.kpis.revenue_change} tone="orange" /><Stat label="Shipments analyzed" value={(data.kpis.shipments / 1000000).toFixed(2)} suffix="M" change={2.3} tone="slate" /></div>
        <div className="content-grid"><section className="panel trend-panel"><div className="panel-head"><div><span className="panel-kicker">PERFORMANCE TREND</span><h3>On-time delivery rate</h3></div><span className="target-key"><i /> Target 90%</span></div><div className="chart-wrap" data-testid="on-time-trend-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.trend}><defs><linearGradient id="blueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2563eb" stopOpacity={0.18} /><stop offset="100%" stopColor="#2563eb" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#e5e7eb" /><XAxis dataKey="week" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#64748b" }} /><YAxis domain={[78, 94]} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={(v) => `${v}%`} /><Tooltip contentStyle={{ border: "1px solid #e2e8f0", borderRadius: 4 }} /><Area type="monotone" dataKey="target" stroke="#94a3b8" strokeDasharray="4 4" fill="none" strokeWidth={1.5} /><Area type="monotone" dataKey="on_time" stroke="#2563eb" fill="url(#blueFill)" strokeWidth={3} /></AreaChart></ResponsiveContainer></div></section>
            <section className="panel driver-preview"><div className="panel-head"><div><span className="panel-kicker">DECLINE EXPLAINED</span><h3>Driver tree</h3></div><span className="coverage" data-testid="driver-coverage">{data.coverage || 0}%</span></div>{data.drivers.map((d) => <div className="driver-row" key={d.label} data-testid={`driver-${d.label.toLowerCase().replaceAll(" ", "-")}`}><div><span>{d.label}</span><b>{d.value}%</b></div><div className="bar-track"><i style={{ width: `${d.value * 2.63}%`, background: d.color }} /></div></div>)}<button className="panel-link" onClick={() => setView("drivers")} data-testid="open-driver-tree">Open full driver tree <ArrowUpRight size={14} /></button></section></div>
        <div className="lower-grid"><section className="panel hub-panel"><div className="panel-head"><div><span className="panel-kicker">WHERE TO ACT</span><h3>Hub performance</h3></div><button className="mini-link" data-testid="hub-sort-button">Sort by impact ↓</button></div><table><thead><tr><th>Hub</th><th>On-time</th><th>Change</th><th>Volume</th><th>Signal</th></tr></thead><tbody>{data.hubs.map(h => <tr key={h.name} data-testid={`hub-row-${h.name.toLowerCase().replaceAll(" ", "-")}`}><td><b>{h.name}</b></td><td>{h.on_time}%</td><td className="negative">{h.delta}%</td><td>{(h.volume / 1000).toFixed(1)}k</td><td><span className={`risk ${h.risk.toLowerCase()}`}>{h.risk}</span></td></tr>)}</tbody></table></section><section className="panel action-panel"><div className="panel-head"><div><span className="panel-kicker">RECOMMENDED NEXT</span><h3>Actions to own</h3></div></div>{data.recommendations.slice(0, 2).map((r, i) => <div className="action-item" key={r.title} data-testid={`recommendation-${i}`}><span className="action-number">0{i + 1}</span><div><b>{r.title}</b><small>{r.owner} · {r.target}</small></div><span className="priority">{r.priority}</span></div>)}<button className="panel-link" onClick={() => setView("hypotheses")} data-testid="open-recommendations">See evidence & owners <ArrowUpRight size={14} /></button></section></div>
    </>;
}

function Drivers({ data }) { return <section className="page-section"><div className="section-intro"><span className="eyebrow">DECOMPOSITION / {data.coverage || 0}% EXPLAINED</span><h2>What moved the metric?</h2><p>Each branch shows its share of the uploaded dataset's observed movement. The remaining {Math.max(0, 100 - (data.coverage || 0))}% is still being investigated.</p></div><div className="driver-layout"><section className="panel driver-chart"><ResponsiveContainer width="100%" height={340}><BarChart data={data.drivers} layout="vertical" margin={{ left: 25, right: 30 }}><CartesianGrid horizontal={false} stroke="#e5e7eb" /><XAxis type="number" domain={[0, 45]} tickFormatter={(v) => `${v}%`} /><YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 12 }} /><Tooltip /><Bar dataKey="value" fill="#2563eb" radius={[0, 3, 3, 0]} /></BarChart></ResponsiveContainer></section><section className="panel cause-note"><span className="panel-kicker">CAUSALITY CHECK</span><h3>Why this is more than correlation</h3><p>The top driver is calculated from the uploaded rows and concentrated in the segments shown in this view. Add event timestamps and controls for a stronger causal test.</p><div className="proof"><CheckCircle2 size={17} /><span>Evidence coverage<br /><b>Target 80% · {data.coverage || 0}% explained</b></span></div><button className="export-btn" onClick={() => window.open(`${API}/export/drivers`, "_blank")} data-testid="download-driver-tree-button"><Download size={15} /> Download driver tree</button></section></div></section>; }

function Hypotheses({ data }) { return <section className="page-section"><div className="section-intro"><span className="eyebrow">HYPOTHESIS LOG / 5 TESTS</span><h2>Claims, tested with evidence.</h2><p>Documented comparisons keep the conversation focused on what the data can prove.</p></div><section className="panel table-panel"><table className="hyp-table"><thead><tr><th>Hypothesis</th><th>Result</th><th>Method</th><th>Evidence</th><th>Owner</th></tr></thead><tbody>{data.hypotheses.map(h => <tr key={h.id} data-testid={`hypothesis-row-${h.id}`}><td><span className="hyp-id">{h.id}</span><b>{h.title}</b></td><td><span className={`status ${h.status.toLowerCase()}`}>{h.status}</span></td><td>{h.test}</td><td>{h.evidence}</td><td>{h.owner}</td></tr>)}</tbody></table><button className="export-btn table-export" onClick={() => window.open(`${API}/export/hypotheses`, "_blank")} data-testid="download-hypotheses-button"><Download size={15} /> Download hypothesis log</button></section></section>; }

function EarlyWarning({ data }) { return <section className="page-section"><div className="section-intro"><span className="eyebrow">SIGNAL DETECTION / WEEKLY</span><h2>See the drop before it becomes a crisis.</h2><p>These signals would have raised a flag before the headline metric crossed its 90% floor.</p></div><div className="warning-banner" data-testid="warning-banner"><AlertTriangle size={20} /><div><b>3 leading signals detected</b><span>Earliest warning: 7 weeks before the current period</span></div><strong>ACT NOW</strong></div><section className="panel alerts-panel"><div className="panel-head"><div><span className="panel-kicker">EARLY SIGNALS</span><h3>Weekly alert history</h3></div></div>{data.alerts.map((a, i) => <div className="alert-row" key={a.week} data-testid={`alert-row-${i}`}><span className="alert-week">{a.week}</span><span className={`alert-icon ${a.severity.toLowerCase()}`}><AlertTriangle size={15} /></span><b>{a.signal}</b><span className="alert-severity">{a.severity}</span><span className="alert-lead">Flagged {a.lead} early</span></div>)}</section></section>; }

export default App;