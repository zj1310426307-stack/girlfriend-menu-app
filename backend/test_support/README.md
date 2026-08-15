# Test and diagnostic database isolation

Database-touching experiments should be pytest tests whenever possible. The
root `tests/conftest.py` activates a UUID-named SQLite database before any
application import, verifies that the default development database stays
unchanged, and cleans only the database it owns.

A necessary standalone diagnostic must run from `backend/` and call the shared
bootstrap before importing `database`, `main`, `models`, or any service:

```python
from pathlib import Path

from test_support.database_isolation import create_isolated_database

isolation = create_isolated_database(root=Path(".test-tmp") / "my-diagnostic")
isolation.activate()

import database  # application imports belong below isolation.activate()

try:
    # Run the bounded diagnostic through the existing database boundary.
    pass
finally:
    database.engine.dispose()
    isolation.cleanup()
```

Do not duplicate `os.environ["DATABASE_URL"]` setup in temporary scripts. The
helper refuses late activation, pre-existing files, production-style URLs,
the default development database, and dangerous cleanup roots. Production,
backup, migration, and acceptance tools must continue to select their real
database explicitly and must not use this test-only helper.
