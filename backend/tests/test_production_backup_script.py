"""Regression coverage for the legacy production logical-backup exporter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backup_production_api.py"
SPEC = importlib.util.spec_from_file_location("backup_production_api", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


def test_backup_uses_admin_orders_embedded_reviews(monkeypatch, tmp_path):
    """Admin backup must never call the customer-owned review detail route."""
    api_origin = "https://production.example"
    orders = [
        {"id": 3, "review": {"id": 30, "rating": 5}},
        {"id": 4, "review": None},
    ]
    requested_paths: list[str] = []

    def fake_request_json(origin, path, *, method="GET", body=None, token=None):
        assert origin == api_origin
        requested_paths.append(path)
        if "/review" in path:
            raise AssertionError("backup called the customer-owned review endpoint")
        if path == "/api/admin/login":
            assert method == "POST"
            assert body == {"password": "password", "invite_code": "invite"}
            return {"token": "admin-token"}
        if path == "/api/orders":
            assert token == "admin-token"
            return orders
        if path == "/api/health":
            return {"status": "ok"}
        if path == "/api/dishes":
            return [{"id": 1}]
        if path.startswith("/api/stats/"):
            assert token == "admin-token"
            return {"ok": True}
        raise AssertionError(f"unexpected request path: {path}")

    monkeypatch.setenv("PRODUCTION_API_ORIGIN", api_origin)
    monkeypatch.setenv("ADMIN_PASSWORD", "password")
    monkeypatch.setenv("ADMIN_INVITE_CODE", "invite")
    monkeypatch.setattr(backup, "ROOT", tmp_path)
    monkeypatch.setattr(backup, "request_json", fake_request_json)

    assert backup.main() == 0

    backup_paths = list((tmp_path / "backups").glob("*.json"))
    data_path = next(path for path in backup_paths if not path.name.endswith(".manifest.json"))
    manifest_path = data_path.with_suffix(".manifest.json")
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["reviews"] == {"3": orders[0]["review"], "4": None}
    assert manifest["counts"] == {"dishes": 1, "orders": 2, "reviews": 1}
    assert all("/review" not in path for path in requested_paths)
