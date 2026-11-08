import io
import os

import requests


BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def upload(name, csv_text):
    response = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": (name, io.BytesIO(csv_text.encode()), "text/csv")},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_two_uploads_recalculate_and_exports_follow_latest():
    first = upload(
        "TEST_first.csv",
        "on_time,delivery_status,revenue,hub,delay_reason\n"
        "yes,complete,100,North,Traffic\n"
        "no,complete,200,South,Weather\n",
    )
    assert first["kpis"] == {
        "on_time": 50.0,
        "on_time_change": -40.0,
        "success": 100.0,
        "success_change": 2.0,
        "revenue": 150,
        "revenue_change": 0,
        "shipments": 2,
    }
    second = upload(
        "TEST_second.csv",
        "on_time,delivery_status,revenue,hub,delay_reason\n"
        "no,failed,900,East,Weather\n"
        "no,failed,1100,West,Weather\n",
    )
    latest = requests.get(f"{BASE_URL}/api/analytics", timeout=20).json()
    assert latest["kpis"] == second["kpis"]
    assert latest["kpis"]["on_time"] == 0.0
    assert latest["kpis"]["success"] == 0.0
    assert latest["kpis"]["revenue"] == 1000
    assert {row["name"] for row in latest["hubs"]} >= {"East", "West"}
    drivers = requests.get(f"{BASE_URL}/api/export/drivers", timeout=20).text
    hypotheses = requests.get(f"{BASE_URL}/api/export/hypotheses", timeout=20).text
    memo = requests.get(f"{BASE_URL}/api/export/memo", timeout=20).text
    assert "Weather,100%" in drivers
    assert "0.0 point gap" in hypotheses
    assert "83.8" not in memo


def test_upload_without_on_time_field_is_clear_400():
    response = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("TEST_invalid.csv", io.BytesIO(b"hub,revenue\nNorth,10\n"), "text/csv")},
        timeout=20,
    )
    assert response.status_code == 400
    assert "on-time field" in response.json()["detail"]