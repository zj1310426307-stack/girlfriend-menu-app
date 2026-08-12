"""Static release gates that do not contact external services."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
render = (ROOT / "render.yaml").read_text(encoding="utf-8")
required = ("APP_ENV", "production", "UPLOAD_PROVIDER", "CUSTOMER_INVITE_CODE")
missing = [value for value in required if value not in render]
if missing:
    raise SystemExit(f"render.yaml release configuration missing: {missing}")
if not any(provider in render for provider in ("value: database", "value: s3")):
    raise SystemExit("render.yaml must select a durable database or s3 upload provider")
source = (ROOT / "miniprogram" / "src" / "api" / "index.js").read_text(encoding="utf-8")
if "girlfriend-menu-api.onrender.com" in source:
    raise SystemExit("Production API origin is still hard-coded in miniprogram source")
print("release configuration checks passed")
