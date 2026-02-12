"""Database connection and session management."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Database URL from environment, no default (must be configured)
DATABASE_URL = os.environ.get("TODO_DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "TODO_DATABASE_URL environment variable is required. "
        "Example: export TODO_DATABASE_URL='postgresql://localhost/grove'"
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session with automatic cleanup.

    Usage:
        with get_session() as session:
            session.query(Task).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize database tables."""
    from grove.models import Base
    Base.metadata.create_all(bind=engine)


# Dew (personal data) connection — lazy init
_dew_engine = None
_DewSessionLocal = None


def _init_dew_engine():
    """Initialize the dew engine on first use."""
    global _dew_engine, _DewSessionLocal
    import click
    from urllib.parse import urlparse, urlunparse

    password = os.environ.get("GV_DEW_PASSWORD")
    if not password:
        raise click.ClickException(
            "Personal data access requires GV_DEW_PASSWORD.\n"
            "Set it in your shell: export GV_DEW_PASSWORD='...'\n"
            "This is intentionally not set in automated agent environments."
        )

    # Build URL: replace user/password in the existing DATABASE_URL
    parsed = urlparse(DATABASE_URL)
    dew_url = urlunparse(parsed._replace(
        netloc=f"grove_dew:{password}@{parsed.hostname}:{parsed.port or 5432}"
    ))

    _dew_engine = create_engine(dew_url)
    _DewSessionLocal = sessionmaker(bind=_dew_engine, autocommit=False, autoflush=False)


@contextmanager
def get_dew_session() -> Generator[Session, None, None]:
    """Get a session for personal data queries (obsidian, apple_notes).

    Requires GV_DEW_PASSWORD env var. Connects as grove_dew role
    with read-only access to personal schemas.
    """
    global _dew_engine, _DewSessionLocal
    if _dew_engine is None:
        _init_dew_engine()

    session = _DewSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
