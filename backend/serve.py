"""Single-process free-tier entry point for database preparation and Uvicorn."""

import logging
import os

import uvicorn

from services.free_runtime_service import prepare_free_runtime


logger = logging.getLogger(__name__)


def _port() -> int:
    """Parse Render's assigned port while retaining a useful local default."""
    return int(os.environ.get("PORT", "8000"))


def main() -> None:
    """Prepare the database through the free fast path, then serve in this process."""
    logging.basicConfig(level=logging.INFO)
    preparation = prepare_free_runtime()
    # Alembic configures logging during a real migration, so restore the serving
    # logger before emitting the privacy-safe preparation result.
    logging.basicConfig(level=logging.INFO, force=True)
    logger.info(
        "free_runtime_ready schema_changed=%s reference_data_seeded=%s total_ms=%s",
        preparation["schema_changed"],
        preparation["reference_data_seeded"],
        preparation["total_ms"],
    )
    logger.info("starting_uvicorn")
    # Uvicorn's default access logger prints the raw URL. The application
    # middleware already emits a route-template log with equivalent metrics.
    uvicorn.run("main:app", host="0.0.0.0", port=_port(), access_log=False)


if __name__ == "__main__":
    main()
