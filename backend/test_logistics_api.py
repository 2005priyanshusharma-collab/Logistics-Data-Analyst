import io
import os

import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def test_analytics_contract():
    response = requests.get(f"{BASE_URL}/api/analytics", timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert data["kpis"]["on_time"] == 83.8
    assert data["kpis"]["shipments"] == 1482360
    assert len(data["trend"]) == 12
    assert len(data["drivers"]) == 4


def test_exports_contract():
    for kind, content_type in (("memo", "text/plain"), ("drivers", "text/csv"), ("hypotheses", "text/csv")):
        response = requests.get(f"{BASE_URL}/api/export/{kind}", timeout=20)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]
        assert len(response.content) > 20
        assert "attachment" in response.headers.get("content-disposition", "")


def test_upload_updates_count_and_source():
    payload = "week,on_time\nWk 1,90\nWk 2,89\n"
    response = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("TEST_logistics.csv", io.BytesIO(payload.encode()), "text/csv")},
        timeout=20,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["kpis"]["shipments"] == 2
    assert "Uploaded dataset" in data["source"]


def test_upload_rejects_non_csv():
    response = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("TEST_logistics.txt", io.BytesIO(b"not csv"), "text/plain")},
        timeout=20,
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]