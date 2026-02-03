"""Tests to verify database isolation.

These tests confirm that:
1. Tests are running against grove_test, not production
2. Database operations work correctly
3. Test data doesn't leak between tests
"""

import os

from sqlalchemy import text

from grove.db import DATABASE_URL, engine
from grove.models import Grove, Bud


def test_using_test_database():
    """Verify we're connected to the test database, not production."""
    assert "grove_test" in DATABASE_URL, (
        f"DANGER: Tests running against wrong database! "
        f"Expected grove_test, got: {DATABASE_URL}"
    )


def test_env_var_is_test_db():
    """Double-check the env var was set correctly."""
    url = os.environ.get("TODO_DATABASE_URL", "")
    assert "grove_test" in url


def test_can_create_grove(session, clean_tables):
    """Verify we can create a grove in the test database."""
    grove = Grove(name="Test Grove", description="For testing")
    session.add(grove)
    session.commit()

    # Query it back
    result = session.query(Grove).filter_by(name="Test Grove").first()
    assert result is not None
    assert result.description == "For testing"


def test_can_create_bud(session, clean_tables):
    """Verify we can create a bud (task) in the test database."""
    bud = Bud(title="Test Bud", status="seed")
    session.add(bud)
    session.commit()

    result = session.query(Bud).filter_by(title="Test Bud").first()
    assert result is not None
    assert result.status == "seed"


def test_clean_tables_fixture_works(session, clean_tables):
    """Verify the clean_tables fixture actually cleans tables."""
    # After clean_tables runs, there should be no groves
    count = session.execute(text("SELECT COUNT(*) FROM todos.groves")).scalar()
    assert count == 0
