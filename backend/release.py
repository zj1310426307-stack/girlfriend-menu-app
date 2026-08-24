"""Deployment entry point for reference data after Alembic reaches head."""

from services.startup_service import seed_reference_data


def main() -> None:
    """Run the idempotent release preparation outside the serving process."""
    seed_reference_data()


if __name__ == "__main__":
    main()
