"""Free PostgreSQL CI and fail-closed staging readiness contracts."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "check_staging_readiness.py"
SPEC = spec_from_file_location("check_staging_readiness", SCRIPT_PATH)
assert SPEC and SPEC.loader
staging_gate = module_from_spec(SPEC)
SPEC.loader.exec_module(staging_gate)


def _ready_payload(*, wechat_status: str = "optional-disabled") -> dict[str, object]:
    return {
        "status": "ready",
        "database": "postgresql",
        "redis": "optional-disabled",
        "storage": {"provider": "database", "status": "ready", "missing": []},
        "wechat_login": {"status": wechat_status, "missing": []},
        "authentication": {"status": "ready", "missing": []},
    }


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "http://staging.example.com",
        "https://user:secret@staging.example.com",
        "https://staging.example.com/api",
        "https://staging.example.com?target=production",
        "https://staging.example.com#fragment",
        "https://staging.example.com:8443",
        "https://localhost",
        "https://127.0.0.1",
        "https://staging.internal",
    ],
)
def test_staging_origin_rejects_unsafe_targets_before_networking(origin):
    with pytest.raises(staging_gate.StagingReadinessError):
        staging_gate.validate_staging_origin(
            origin, "https://girlfriend-menu-api.onrender.com"
        )


def test_staging_origin_rejects_production_reuse_and_normalizes_host():
    production = "https://girlfriend-menu-api.onrender.com"
    with pytest.raises(staging_gate.StagingReadinessError):
        staging_gate.validate_staging_origin(f"{production}/", production)
    assert (
        staging_gate.validate_staging_origin(
            "https://STAGING.EXAMPLE.COM/", production
        )
        == "https://staging.example.com"
    )
    with pytest.raises(staging_gate.StagingReadinessError):
        staging_gate.validate_staging_origin("https://staging.example.com", "")


def test_read_only_gate_requests_only_health_and_readiness():
    calls = []
    responses = iter(
        [
            {"status": "ok", "service": "girlfriend-menu-api"},
            _ready_payload(),
        ]
    )

    def fetch_json(url, *, timeout, label):
        calls.append((url, timeout, label))
        return next(responses)

    summary = staging_gate.run_checks(
        "https://staging.example.com", timeout=3, fetch_json=fetch_json
    )

    assert calls == [
        ("https://staging.example.com/api/health", 3, "health"),
        ("https://staging.example.com/api/ready", 3, "readiness"),
    ]
    assert summary == {
        "database": "postgresql",
        "redis": "optional-disabled",
        "storage": "ready",
        "authentication": "ready",
        "wechat_login": "optional-disabled",
    }


def test_wechat_can_be_optional_for_infrastructure_then_required_for_device_gate():
    payload = _ready_payload()
    assert staging_gate.validate_readiness(payload, require_wechat=False)[
        "wechat_login"
    ] == "optional-disabled"
    with pytest.raises(staging_gate.StagingReadinessError):
        staging_gate.validate_readiness(payload, require_wechat=True)
    assert staging_gate.validate_readiness(
        _ready_payload(wechat_status="ready"), require_wechat=True
    )["wechat_login"] == "ready"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(status="release-blocked"),
        lambda payload: payload.update(database="sqlite"),
        lambda payload: payload["storage"].update(status="release-blocked"),
        lambda payload: payload["storage"].update(provider="local"),
        lambda payload: payload["authentication"].update(missing=["ADMIN_SECRET"]),
        lambda payload: payload.update(redis="invalid"),
    ],
)
def test_readiness_gate_rejects_non_releaseable_components(mutation):
    payload = _ready_payload(wechat_status="ready")
    mutation(payload)
    with pytest.raises(staging_gate.StagingReadinessError):
        staging_gate.validate_readiness(payload, require_wechat=True)


def test_ci_keeps_sqlite_and_postgresql_migration_matrices():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "image: postgres:18-alpine" in workflow
    assert "DATABASE_URL=sqlite:///migration_ci.db" in workflow
    postgres_url = (
        "DATABASE_URL=postgresql+psycopg2://"
        "postgres:postgres@127.0.0.1:5432/migration_ci"
    )
    assert workflow.count(postgres_url) == 6
    assert f"{postgres_url} python -m alembic -c alembic.ini downgrade -1" in workflow
    assert f"{postgres_url} python -m alembic -c alembic.ini downgrade base" in workflow
    assert (
        f"{postgres_url} python -m alembic -c alembic.ini upgrade 20260808_01"
        in workflow
    )
