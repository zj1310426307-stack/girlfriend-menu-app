"""Deployment preparation stays outside the latency-sensitive serving path."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from services import free_runtime_service
from services import startup_service


def test_reference_seed_order_and_bounded_timing(monkeypatch):
    """Run every idempotent catalogue seed once through one owned DB session."""
    calls = []
    session = object()

    class _SessionScope:
        def __enter__(self):
            return session

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(startup_service, "SessionLocal", _SessionScope)
    targets = (
        (startup_service, "seed_dishes", "dishes"),
        (startup_service, "seed_games", "games"),
        (startup_service, "seed_game_events", "game_events"),
        (startup_service, "seed_achievements", "achievements"),
        (startup_service.game_data_service, "ensure_ai_catalog", "ai_catalog"),
        (startup_service.user_service, "seed_system_users", "system_users"),
    )
    for owner, attribute, label in targets:
        monkeypatch.setattr(
            owner,
            attribute,
            lambda db, stage=label: calls.append((stage, db)),
        )

    durations = startup_service.seed_reference_data()

    assert calls == [(label, session) for _, _, label in targets]
    assert set(durations) == {*(label for _, _, label in targets), "total"}
    assert all(duration >= 0 for duration in durations.values())


def test_serving_process_has_no_managed_environment_seed_path():
    """Keep managed preparation before Uvicorn and every Blueprint on the free path."""
    root = Path(__file__).resolve().parents[1]
    main_source = (root / "main.py").read_text(encoding="utf-8")
    serve_source = (root / "serve.py").read_text(encoding="utf-8")
    production_render = (root.parent / "render.yaml").read_text(encoding="utf-8")
    oregon_render = (root.parent / "render.production-oregon.yaml").read_text(
        encoding="utf-8"
    )
    assert "if not get_settings().uses_managed_schema" in main_source
    assert "prepare_free_runtime()" in serve_source
    assert "startCommand: python serve.py" in production_render
    assert "plan: free" in production_render
    assert "plan: free" in oregon_render
    assert "plan: starter" not in production_render + oregon_render
    assert "preDeployCommand:" not in production_render + oregon_render


def test_free_runtime_fast_path_skips_migrations_and_reference_scans(monkeypatch):
    """Ordinary free-tier wakes should use only the bounded readiness query."""
    calls = []
    monkeypatch.setattr(
        free_runtime_service,
        "_read_runtime_state",
        lambda: {
            "schema_head": free_runtime_service.EXPECTED_SCHEMA_HEAD,
            "reference_data_ready": True,
            "counts": {},
        },
    )
    monkeypatch.setattr(
        free_runtime_service,
        "_upgrade_schema",
        lambda: calls.append("upgrade"),
    )
    monkeypatch.setattr(
        free_runtime_service,
        "_seed_reference_data",
        lambda: calls.append("seed"),
    )

    result = free_runtime_service.prepare_free_runtime()

    assert calls == []
    assert result["schema_changed"] is False
    assert result["reference_data_seeded"] is False


def test_free_runtime_repairs_drift_then_verifies_the_release_baseline(monkeypatch):
    """A new or partial database must still migrate, seed and verify before serving."""
    states = iter(
        [
            {"schema_head": "", "reference_data_ready": False, "counts": {}},
            {
                "schema_head": free_runtime_service.EXPECTED_SCHEMA_HEAD,
                "reference_data_ready": True,
                "counts": {},
            },
        ]
    )
    calls = []
    monkeypatch.setattr(free_runtime_service, "_read_runtime_state", lambda: next(states))
    monkeypatch.setattr(
        free_runtime_service,
        "_upgrade_schema",
        lambda: calls.append("upgrade"),
    )
    monkeypatch.setattr(
        free_runtime_service,
        "_seed_reference_data",
        lambda: calls.append("seed") or {"total": 1.0},
    )

    result = free_runtime_service.prepare_free_runtime()

    assert calls == ["upgrade", "seed"]
    assert result["schema_changed"] is True
    assert result["reference_data_seeded"] is True


def test_free_runtime_expected_head_matches_the_alembic_graph():
    """Prevent the cheap readiness constant from drifting behind a new migration."""
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == free_runtime_service.EXPECTED_SCHEMA_HEAD
