"""Tests for automatic activity logging on status changes."""

import pytest
from click.testing import CliRunner

from grove.cli import main
from grove.models import Bud, ActivityLog


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def seed_bud(session, clean_tables):
    """Create a bud in seed status."""
    bud = Bud(title="Test Bud", status="seed")
    session.add(bud)
    session.commit()
    return bud


@pytest.fixture
def budding_bud(session, clean_tables):
    """Create a bud in budding status."""
    bud = Bud(title="Test Bud", status="budding")
    session.add(bud)
    session.commit()
    return bud


class TestBloomAutoLogging:
    """Tests for bloom command auto-logging."""

    def test_bloom_logs_status_change(self, runner, session, budding_bud):
        """Bloom command logs status change."""
        result = runner.invoke(main, ["bloom", str(budding_bud.id)])

        assert result.exit_code == 0

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == budding_bud.id,
            ActivityLog.event_type == "status_changed"
        ).first()

        assert activity is not None
        assert "→ bloomed" in activity.content

    def test_done_alias_logs_status_change(self, runner, session, budding_bud):
        """Done alias also logs status change."""
        result = runner.invoke(main, ["done", str(budding_bud.id)])

        assert result.exit_code == 0

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == budding_bud.id,
            ActivityLog.event_type == "status_changed"
        ).first()

        assert activity is not None
        assert "→ bloomed" in activity.content


class TestMulchAutoLogging:
    """Tests for mulch command auto-logging."""

    def test_mulch_logs_status_change(self, runner, session, budding_bud):
        """Mulch command logs status change."""
        result = runner.invoke(main, ["mulch", str(budding_bud.id)])

        assert result.exit_code == 0

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == budding_bud.id,
            ActivityLog.event_type == "status_changed"
        ).first()

        assert activity is not None
        assert "→ mulch" in activity.content


class TestStartAutoLogging:
    """Tests for start command auto-logging."""

    def test_start_logs_status_change(self, runner, session, seed_bud):
        """Start command logs status change."""
        # First plant the seed to make it dormant
        runner.invoke(main, ["plant", str(seed_bud.id)])

        # Clear the plant activity
        session.query(ActivityLog).delete()
        session.commit()

        # Now start it
        result = runner.invoke(main, ["start", str(seed_bud.id)])

        assert result.exit_code == 0

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == seed_bud.id,
            ActivityLog.event_type == "status_changed"
        ).first()

        assert activity is not None
        assert "→ budding" in activity.content


class TestPlantAutoLogging:
    """Tests for plant command auto-logging."""

    def test_plant_logs_status_change(self, runner, session, seed_bud):
        """Plant command logs status change."""
        result = runner.invoke(main, ["plant", str(seed_bud.id)])

        assert result.exit_code == 0

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == seed_bud.id,
            ActivityLog.event_type == "status_changed"
        ).first()

        assert activity is not None
        assert "seed → dormant" in activity.content


class TestSessionIdTracking:
    """Tests for session ID tracking in auto-logs."""

    def test_auto_log_captures_session_id(self, runner, session, budding_bud, monkeypatch):
        """Auto-logged entries capture CLAUDE_SESSION_ID."""
        test_uuid = "12345678-1234-5678-1234-567812345678"
        monkeypatch.setenv("CLAUDE_SESSION_ID", test_uuid)

        # Pass env to runner so it picks up the session ID
        runner.invoke(main, ["bloom", str(budding_bud.id)], env={"CLAUDE_SESSION_ID": test_uuid})

        session.expire_all()
        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == budding_bud.id
        ).first()

        assert activity is not None
        assert str(activity.session_id) == test_uuid

    def test_auto_log_without_session_id(self, runner, session, budding_bud, monkeypatch):
        """Auto-logged entries work without CLAUDE_SESSION_ID."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)

        runner.invoke(main, ["bloom", str(budding_bud.id)])

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == budding_bud.id
        ).first()

        assert activity is not None
        assert activity.session_id is None
