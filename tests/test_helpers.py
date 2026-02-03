"""Tests for CLI helper functions."""

import pytest
import click

from grove.cli import parse_item_ref, get_item_by_ref
from grove.models import Grove, Trunk, Branch, Bud


class TestParseItemRef:
    """Tests for parse_item_ref function."""

    def test_parse_bud_ref(self):
        """Parse bud reference."""
        item_type, item_id = parse_item_ref("b:45")
        assert item_type == "bud"
        assert item_id == 45

    def test_parse_branch_ref(self):
        """Parse branch reference."""
        item_type, item_id = parse_item_ref("br:12")
        assert item_type == "branch"
        assert item_id == 12

    def test_parse_trunk_ref(self):
        """Parse trunk reference."""
        item_type, item_id = parse_item_ref("t:3")
        assert item_type == "trunk"
        assert item_id == 3

    def test_parse_grove_ref(self):
        """Parse grove reference."""
        item_type, item_id = parse_item_ref("g:1")
        assert item_type == "grove"
        assert item_id == 1

    def test_invalid_prefix_raises(self):
        """Invalid prefix raises BadParameter."""
        with pytest.raises(click.BadParameter):
            parse_item_ref("x:5")

    def test_missing_colon_raises(self):
        """Missing colon raises BadParameter."""
        with pytest.raises(click.BadParameter):
            parse_item_ref("b5")

    def test_non_numeric_id_raises(self):
        """Non-numeric ID raises BadParameter."""
        with pytest.raises(click.BadParameter):
            parse_item_ref("b:abc")

    def test_empty_string_raises(self):
        """Empty string raises BadParameter."""
        with pytest.raises(click.BadParameter):
            parse_item_ref("")


class TestGetItemByRef:
    """Tests for get_item_by_ref function."""

    def test_get_grove(self, session, clean_tables):
        """Get grove by ref."""
        grove = Grove(name="Test Grove")
        session.add(grove)
        session.commit()

        result, model = get_item_by_ref(session, "grove", grove.id)
        assert result is not None
        assert result.name == "Test Grove"
        assert model == Grove

    def test_get_trunk(self, session, clean_tables):
        """Get trunk by ref."""
        trunk = Trunk(title="Test Trunk")
        session.add(trunk)
        session.commit()

        result, model = get_item_by_ref(session, "trunk", trunk.id)
        assert result is not None
        assert result.title == "Test Trunk"

    def test_get_branch(self, session, clean_tables):
        """Get branch by ref."""
        branch = Branch(title="Test Branch")
        session.add(branch)
        session.commit()

        result, model = get_item_by_ref(session, "branch", branch.id)
        assert result is not None
        assert result.title == "Test Branch"

    def test_get_bud(self, session, clean_tables):
        """Get bud by ref."""
        bud = Bud(title="Test Bud", status="seed")
        session.add(bud)
        session.commit()

        result, model = get_item_by_ref(session, "bud", bud.id)
        assert result is not None
        assert result.title == "Test Bud"

    def test_nonexistent_item_returns_none(self, session, clean_tables):
        """Nonexistent item returns None."""
        result, model = get_item_by_ref(session, "bud", 99999)
        assert result is None

    def test_invalid_type_returns_none(self, session):
        """Invalid item type returns None."""
        result, model = get_item_by_ref(session, "invalid", 1)
        assert result is None
