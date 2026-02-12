"""Pytest configuration for Grove tests.

IMPORTANT: This file sets TODO_DATABASE_URL BEFORE importing grove modules.
This ensures tests ALWAYS use the test database, not production.

The test database is hardcoded here - it's not configurable via env vars.
This prevents any possibility of accidentally running tests against prod.
"""

import os

# Set test database URL BEFORE any grove imports
# This is intentionally hardcoded - tests should ONLY ever use this database
TEST_DATABASE_URL = "postgresql://localhost/grove_test"
os.environ["TODO_DATABASE_URL"] = TEST_DATABASE_URL

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text

# Now safe to import grove modules (they'll use the test DB)
from grove.db import engine, get_session


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Apply schema and migrations to test database once per test session.

    This runs automatically before any tests execute.
    Drops and recreates all tables for a clean slate.
    """
    schema_path = Path(__file__).parent.parent / "sql" / "schema.sql"
    migrations_dir = Path(__file__).parent.parent / "sql"

    # Drop tables not in base schema before applying (they're in migrations)
    subprocess.run(
        ["psql", "-d", "grove_test", "-c",
         "DROP TABLE IF EXISTS todos.activity_log CASCADE; "
         "DROP TABLE IF EXISTS todos.refs CASCADE; "
         "DROP TABLE IF EXISTS todos.bead_links CASCADE; "
         "DROP TABLE IF EXISTS todos.pollen CASCADE; "
         "DROP TABLE IF EXISTS todos.dew CASCADE;"],
        capture_output=True,
        text=True,
    )

    # Apply base schema using psql for proper SQL execution
    result = subprocess.run(
        ["psql", "-d", "grove_test", "-f", str(schema_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to apply schema: {result.stderr}")

    # Apply migrations in order
    migrations = [
        "002_bead_links.sql",
        "003_activity_refs.sql",
        "004_roots.sql",
        "005_branch_nesting.sql",
        "006_rename_branch_to_stem.sql",
        "007_pollen_dew.sql",
    ]
    for migration in migrations:
        migration_path = migrations_dir / migration
        if migration_path.exists():
            result = subprocess.run(
                ["psql", "-d", "grove_test", "-f", str(migration_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.fail(f"Failed to apply migration {migration}: {result.stderr}")

    yield

    # Cleanup happens via schema.sql DROP statements on next run


@pytest.fixture
def session():
    """Provide a database session for tests.

    Each test gets a fresh session. Changes are rolled back after each test
    to keep tests isolated.
    """
    with get_session() as sess:
        yield sess
        # Rollback is handled by get_session context manager on exception
        # For test isolation, we explicitly rollback
        sess.rollback()


@pytest.fixture
def clean_tables(session):
    """Truncate all tables for tests that need a completely clean state.

    Use this fixture when you need to ensure no data exists from other tests.
    """
    # Truncate in reverse dependency order
    tables = [
        "todos.pollen",
        "todos.dew",
        "todos.activity_log",
        "todos.refs",
        "todos.bead_links",
        "todos.habit_log",
        "todos.habits",
        "todos.bud_dependencies",
        "todos.buds",
        "todos.stems",
        "todos.fruits",
        "todos.trunks",
        "todos.groves",
    ]

    for table in tables:
        session.execute(text(f"TRUNCATE {table} CASCADE"))

    session.commit()
    yield
