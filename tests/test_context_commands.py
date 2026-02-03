"""Tests for AI context commands (context, log, ref, activity)."""

import os
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner

from grove.cli import main
from grove.models import Grove, Trunk, Branch, Bud, ActivityLog, Ref


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_hierarchy(session, clean_tables):
    """Create a sample hierarchy for testing."""
    grove = Grove(name="Test Grove", icon="🌳")
    session.add(grove)
    session.flush()

    trunk = Trunk(title="Test Trunk", grove_id=grove.id)
    session.add(trunk)
    session.flush()

    branch = Branch(title="Test Branch", trunk_id=trunk.id)
    session.add(branch)
    session.flush()

    bud = Bud(title="Test Bud", status="seed", branch_id=branch.id)
    session.add(bud)
    session.commit()

    return {"grove": grove, "trunk": trunk, "branch": branch, "bud": bud}


class TestContextCommand:
    """Tests for gv context command."""

    def test_context_shows_bud_info(self, runner, sample_hierarchy):
        """Context command shows bud information."""
        bud = sample_hierarchy["bud"]
        result = runner.invoke(main, ["context", f"b:{bud.id}"])

        assert result.exit_code == 0
        assert "Test Bud" in result.output
        assert "seed" in result.output

    def test_context_shows_hierarchy(self, runner, sample_hierarchy):
        """Context command shows parent hierarchy."""
        bud = sample_hierarchy["bud"]
        result = runner.invoke(main, ["context", f"b:{bud.id}"])

        assert result.exit_code == 0
        assert "Test Branch" in result.output

    def test_context_brief_mode(self, runner, sample_hierarchy):
        """Brief mode shows condensed output."""
        bud = sample_hierarchy["bud"]
        result = runner.invoke(main, ["context", f"b:{bud.id}", "--brief"])

        assert result.exit_code == 0
        # Brief output should be shorter
        assert len(result.output.split("\n")) < 5

    def test_context_updates_last_checked(self, runner, session, sample_hierarchy):
        """Context updates last_checked_at by default."""
        bud = sample_hierarchy["bud"]
        assert bud.last_checked_at is None

        runner.invoke(main, ["context", f"b:{bud.id}"])

        session.refresh(bud)
        assert bud.last_checked_at is not None

    def test_context_peek_does_not_update(self, runner, session, sample_hierarchy):
        """Peek mode does not update last_checked_at."""
        bud = sample_hierarchy["bud"]
        assert bud.last_checked_at is None

        runner.invoke(main, ["context", f"b:{bud.id}", "--peek"])

        session.refresh(bud)
        assert bud.last_checked_at is None

    def test_context_invalid_ref(self, runner):
        """Invalid ref shows error."""
        result = runner.invoke(main, ["context", "invalid"])
        assert result.exit_code == 0  # Click doesn't set exit code for this
        assert "Invalid format" in result.output

    def test_context_nonexistent_item(self, runner, clean_tables):
        """Nonexistent item shows not found."""
        result = runner.invoke(main, ["context", "b:99999"])
        assert "not found" in result.output.lower()


class TestLogCommand:
    """Tests for gv log command."""

    def test_log_creates_activity(self, runner, session, sample_hierarchy):
        """Log command creates activity entry."""
        bud = sample_hierarchy["bud"]

        result = runner.invoke(main, ["log", f"b:{bud.id}", "Test log message"])

        assert result.exit_code == 0
        assert "Logged" in result.output

        # Check activity was created
        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == bud.id,
            ActivityLog.event_type == "log"
        ).first()

        assert activity is not None
        assert activity.content == "Test log message"

    def test_log_invalid_ref(self, runner):
        """Invalid ref shows error."""
        result = runner.invoke(main, ["log", "invalid", "message"])
        assert "Invalid format" in result.output

    def test_log_captures_session_id(self, runner, session, sample_hierarchy, monkeypatch):
        """Log captures CLAUDE_SESSION_ID if set."""
        bud = sample_hierarchy["bud"]
        test_uuid = "12345678-1234-5678-1234-567812345678"
        monkeypatch.setenv("CLAUDE_SESSION_ID", test_uuid)

        # Use env parameter to pass the environment to the CLI runner
        result = runner.invoke(main, ["log", f"b:{bud.id}", "Test message"], env={"CLAUDE_SESSION_ID": test_uuid})
        assert result.exit_code == 0

        # Need to expire the session to see changes from CLI
        session.expire_all()
        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == bud.id,
            ActivityLog.event_type == "log"
        ).first()

        assert activity is not None
        assert str(activity.session_id) == test_uuid


class TestRefCommand:
    """Tests for gv ref command."""

    def test_ref_auto_detects_note(self, runner, session, sample_hierarchy):
        """Ref auto-detects Obsidian note syntax."""
        bud = sample_hierarchy["bud"]

        result = runner.invoke(main, ["ref", f"b:{bud.id}", "[[My Note]]"])

        assert result.exit_code == 0

        ref = session.query(Ref).filter(
            Ref.item_type == "bud",
            Ref.item_id == bud.id
        ).first()

        assert ref is not None
        assert ref.ref_type == "note"
        assert ref.value == "[[My Note]]"

    def test_ref_auto_detects_url(self, runner, session, sample_hierarchy):
        """Ref auto-detects URLs."""
        bud = sample_hierarchy["bud"]

        runner.invoke(main, ["ref", f"b:{bud.id}", "https://example.com"])

        ref = session.query(Ref).filter(Ref.item_id == bud.id).first()
        assert ref.ref_type == "url"

    def test_ref_auto_detects_file(self, runner, session, sample_hierarchy):
        """Ref auto-detects file paths."""
        bud = sample_hierarchy["bud"]

        runner.invoke(main, ["ref", f"b:{bud.id}", "/path/to/file"])

        ref = session.query(Ref).filter(Ref.item_id == bud.id).first()
        assert ref.ref_type == "file"

    def test_ref_explicit_type_overrides(self, runner, session, sample_hierarchy):
        """Explicit type flag overrides auto-detection."""
        bud = sample_hierarchy["bud"]

        runner.invoke(main, ["ref", f"b:{bud.id}", "something", "--note"])

        ref = session.query(Ref).filter(Ref.item_id == bud.id).first()
        assert ref.ref_type == "note"

    def test_ref_with_label(self, runner, session, sample_hierarchy):
        """Ref can have optional label."""
        bud = sample_hierarchy["bud"]

        runner.invoke(main, ["ref", f"b:{bud.id}", "https://github.com", "--label", "Main repo"])

        ref = session.query(Ref).filter(Ref.item_id == bud.id).first()
        assert ref.label == "Main repo"

    def test_ref_logs_activity(self, runner, session, sample_hierarchy):
        """Adding ref creates activity log entry."""
        bud = sample_hierarchy["bud"]

        runner.invoke(main, ["ref", f"b:{bud.id}", "[[Note]]"])

        activity = session.query(ActivityLog).filter(
            ActivityLog.item_type == "bud",
            ActivityLog.item_id == bud.id,
            ActivityLog.event_type == "ref_added"
        ).first()

        assert activity is not None


class TestActivityCommand:
    """Tests for gv activity command."""

    def test_activity_shows_entries(self, runner, session, sample_hierarchy):
        """Activity command shows log entries."""
        bud = sample_hierarchy["bud"]

        # Create some activity
        for i in range(3):
            session.add(ActivityLog(
                item_type="bud",
                item_id=bud.id,
                event_type="log",
                content=f"Message {i}"
            ))
        session.commit()

        result = runner.invoke(main, ["activity", f"b:{bud.id}"])

        assert result.exit_code == 0
        assert "Message 0" in result.output
        assert "Message 1" in result.output
        assert "Message 2" in result.output

    def test_activity_limit(self, runner, session, sample_hierarchy):
        """Activity respects --limit flag."""
        bud = sample_hierarchy["bud"]

        # Create many entries
        for i in range(10):
            session.add(ActivityLog(
                item_type="bud",
                item_id=bud.id,
                event_type="log",
                content=f"Message {i}"
            ))
        session.commit()

        result = runner.invoke(main, ["activity", f"b:{bud.id}", "-n", "3"])

        assert result.exit_code == 0
        # Should show only 3, with note about more
        assert "3 of 10" in result.output

    def test_activity_empty(self, runner, sample_hierarchy):
        """Activity shows message when no entries."""
        bud = sample_hierarchy["bud"]

        result = runner.invoke(main, ["activity", f"b:{bud.id}"])

        assert result.exit_code == 0
        assert "No activity" in result.output
