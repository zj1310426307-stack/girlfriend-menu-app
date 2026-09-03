"""Static release gates that do not contact external services."""

from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
render = (ROOT / "render.yaml").read_text(encoding="utf-8")
staging_render = (ROOT / "render.staging.yaml").read_text(encoding="utf-8")
oregon_render = (ROOT / "render.production-oregon.yaml").read_text(encoding="utf-8")
env_example = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
backup_source = (ROOT / "scripts" / "backup_production_api.py").read_text(
    encoding="utf-8"
)
cloudbase_dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
cloudbase_guide = (
    ROOT / "docs" / "release-v3" / "CLOUDBASE_FREE_STAGING.md"
).read_text(encoding="utf-8")


def has_yaml_setting(source: str, key: str, value: str) -> bool:
    """Match an active scalar setting instead of accepting a comment substring."""
    pattern = rf"(?m)^\s*{re.escape(key)}:\s*{re.escape(value)}\s*(?:#.*)?$"
    return re.search(pattern, source) is not None


def dotenv_values(source: str) -> dict[str, str]:
    """Parse the simple KEY=VALUE environment template used by this project."""
    values = {}
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def getenv_defaults(source: str) -> dict[str, object]:
    """Return literal defaults for environment reads in the production backup tool."""
    defaults = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if (
            not isinstance(node.func.value, ast.Name)
            or node.func.value.id != "os"
            or node.func.attr != "getenv"
            or not node.args
            or not isinstance(node.args[0], ast.Constant)
        ):
            continue
        name = node.args[0].value
        if isinstance(name, str):
            defaults[name] = (
                node.args[1].value
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant)
                else None
            )
    return defaults


required = (
    "APP_ENV",
    "production",
    "UPLOAD_PROVIDER",
    "CUSTOMER_INVITE_CODE",
    "WECHAT_LOGIN_ENABLED",
    "WECHAT_APP_ID",
    "WECHAT_APP_SECRET",
)
missing = [value for value in required if value not in render]
if missing:
    raise SystemExit(f"render.yaml release configuration missing: {missing}")
production_runtime = {
    "plan": "free",
    "startCommand": "python serve.py",
    "autoDeploy": "false",
}
runtime_missing = [
    f"{key}: {value}"
    for key, value in production_runtime.items()
    if not has_yaml_setting(render, key, value)
]
if runtime_missing:
    raise SystemExit(f"render.yaml optimized runtime configuration missing: {runtime_missing}")
if has_yaml_setting(render, "autoDeploy", "true"):
    raise SystemExit("render.yaml production deploys must remain behind the manual gate")
if not any(provider in render for provider in ("value: database", "value: s3")):
    raise SystemExit("render.yaml must select a durable database or s3 upload provider")
staging_required = (
    "girlfriend-menu-api-staging",
    "value: staging",
    "autoDeploy: false",
    "WECHAT_LOGIN_ENABLED",
    "WECHAT_APP_ID",
    "WECHAT_APP_SECRET",
    "UPLOAD_PROVIDER",
)
staging_missing = [value for value in staging_required if value not in staging_render]
if staging_missing:
    raise SystemExit(f"render.staging.yaml isolation configuration missing: {staging_missing}")
cloudbase_required = (
    "FROM python:3.12.11-slim-bookworm",
    "ENV PYTHONDONTWRITEBYTECODE=1",
    "PYTHONUNBUFFERED=1",
    "PORT=80",
    'CMD ["python", "serve.py"]',
)
cloudbase_missing = [value for value in cloudbase_required if value not in cloudbase_dockerfile]
if cloudbase_missing:
    raise SystemExit(f"CloudBase container contract missing: {cloudbase_missing}")
cloudbase_guide_required = (
    "免费体验版",
    "禁止切换付费套餐",
    "DATABASE_URL",
    "独立 Neon staging",
    "MINIPROGRAM_DOMAIN_NOT_ALLOWED",
    "wx.cloud.callContainer",
)
cloudbase_guide_missing = [
    value for value in cloudbase_guide_required if value not in cloudbase_guide
]
if cloudbase_guide_missing:
    raise SystemExit(f"CloudBase free staging guide missing: {cloudbase_guide_missing}")
oregon_required = (
    "girlfriend-menu-api-oregon",
    "plan: free",
    "region: oregon",
    "autoDeploy: false",
    "startCommand: python serve.py",
)
oregon_missing = [value for value in oregon_required if value not in oregon_render]
if oregon_missing:
    raise SystemExit(f"Oregon replacement configuration missing: {oregon_missing}")
for name, blueprint in (
    ("production", render),
    ("staging", staging_render),
    ("oregon", oregon_render),
):
    if not has_yaml_setting(blueprint, "plan", "free"):
        raise SystemExit(f"{name} Blueprint must use the zero-cost free plan")
    if has_yaml_setting(blueprint, "plan", "starter") or "preDeployCommand:" in blueprint:
        raise SystemExit(f"{name} Blueprint must stay on the zero-cost runtime path")

secret_example_keys = (
    "ADMIN_PASSWORD",
    "ADMIN_PASSWORD_HASH",
    "ADMIN_INVITE_CODE",
    "ADMIN_SECRET",
    "CUSTOMER_INVITE_CODE",
    "WECHAT_APP_SECRET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "REDIS_URL",
)
example_values = dotenv_values(env_example)
missing_secret_keys = [key for key in secret_example_keys if key not in example_values]
if missing_secret_keys:
    raise SystemExit(f"backend/.env.example secret fields missing: {missing_secret_keys}")
nonempty_secrets = [key for key in secret_example_keys if example_values[key]]
if nonempty_secrets:
    raise SystemExit(
        f"backend/.env.example secrets must stay blank: {nonempty_secrets}"
    )

release_surfaces = {
    "backend/.env.example": env_example,
    "render.yaml": render,
    "render.staging.yaml": staging_render,
    "render.production-oregon.yaml": oregon_render,
    "scripts/backup_production_api.py": backup_source,
    "backend/Dockerfile": cloudbase_dockerfile,
    "docs/release-v3/CLOUDBASE_FREE_STAGING.md": cloudbase_guide,
}
for unsafe in ("admin123", "love2026", "replace-with"):
    contaminated = [
        name for name, source in release_surfaces.items() if unsafe in source.lower()
    ]
    if contaminated:
        raise SystemExit(
            f"unsafe example value {unsafe!r} found in release surfaces: {contaminated}"
        )

backup_required_env = (
    "PRODUCTION_API_ORIGIN",
    "ADMIN_PASSWORD",
    "ADMIN_INVITE_CODE",
)
backup_defaults = getenv_defaults(backup_source)
missing_backup_env = [name for name in backup_required_env if name not in backup_defaults]
if missing_backup_env:
    raise SystemExit(
        f"production backup explicit environment checks missing: {missing_backup_env}"
    )
unsafe_backup_defaults = {
    name: backup_defaults[name]
    for name in backup_required_env
    if backup_defaults[name] not in (None, "")
}
if unsafe_backup_defaults:
    raise SystemExit(
        f"production backup environment values must not have defaults: {unsafe_backup_defaults}"
    )
validation_marker = (
    "api_origin, admin_password, admin_invite_code = required_configuration()"
)
first_network_marker = "login = request_json("
if (
    validation_marker not in backup_source
    or first_network_marker not in backup_source
    or backup_source.index(validation_marker) > backup_source.index(first_network_marker)
):
    raise SystemExit("production backup must validate all configuration before networking")

source = (ROOT / "miniprogram" / "src" / "api" / "index.js").read_text(encoding="utf-8")
if "girlfriend-menu-api.onrender.com" in source:
    raise SystemExit("Production API origin is still hard-coded in miniprogram source")
staging_env = (ROOT / "miniprogram" / ".env.staging").read_text(encoding="utf-8")
if "girlfriend-menu-api.onrender.com" in staging_env:
    raise SystemExit("Staging mini program must not target the production API")
print("release configuration checks passed")
