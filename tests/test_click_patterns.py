"""Tests for Click scraper enhancements: 1a/1b/1c/1d/1e."""
from __future__ import annotations

import ast
import pytest
from pathlib import Path

from cli2mcp.scrapers.click_scraper import ClickScraper

FIXTURE = Path(__file__).parent / "fixtures" / "sample_click_patterns.py"


@pytest.fixture
def scraper():
    return ClickScraper(source_module="sample_click_patterns", cli_command="mycli")


@pytest.fixture
def tools(scraper):
    return {t.name: t for t in scraper.scrape_file(FIXTURE)}


# ---------------------------------------------------------------------------
# 1a: Custom decorator wrappers
# ---------------------------------------------------------------------------

class TestDecoratorWrappers:
    def test_train_has_dataset_param(self, tools):
        """dataset_option wrapper should expand --dataset into the tool."""
        assert "train" in tools
        params = {p.name: p for p in tools["train"].parameters}
        assert "dataset" in params, "dataset param from dataset_option wrapper not found"

    def test_train_has_version_param(self, tools):
        assert "train" in tools
        params = {p.name: p for p in tools["train"].parameters}
        assert "version" in params

    def test_train_version_type(self, tools):
        params = {p.name: p for p in tools["train"].parameters}
        assert params["version"].type_annotation == "int"

    def test_export_has_all_wrapper_params(self, tools):
        """export uses both dataset_option and output_options wrappers."""
        assert "export" in tools
        params = {p.name: p for p in tools["export"].parameters}
        # From dataset_option
        assert "dataset" in params
        assert "version" in params
        # From output_options
        assert "output_dir" in params
        assert "dry_run" in params

    def test_export_dry_run_is_flag(self, tools):
        params = {p.name: p for p in tools["export"].parameters}
        assert params["dry_run"].is_flag is True


# ---------------------------------------------------------------------------
# 1b: @click.pass_context
# ---------------------------------------------------------------------------

class TestPassContext:
    def test_create_has_context_flag(self, tools):
        """Commands with @click.pass_context should have has_context=True."""
        assert "create" in tools
        assert tools["create"].has_context is True

    def test_create_ctx_not_in_params(self, tools):
        """The ctx argument must NOT appear in the tool parameters."""
        params = {p.name: p for p in tools["create"].parameters}
        assert "ctx" not in params

    def test_create_name_param_present(self, tools):
        """Real params after ctx should still be captured."""
        params = {p.name: p for p in tools["create"].parameters}
        assert "name" in params
        assert params["name"].required is True

    def test_non_context_commands_have_false(self, tools):
        """Commands without pass_context should have has_context=False."""
        assert tools["train"].has_context is False


# ---------------------------------------------------------------------------
# 1c: async def commands
# ---------------------------------------------------------------------------

class TestAsyncCommands:
    def test_async_fetch_discovered(self, tools):
        """async def commands should be scraped just like regular def."""
        assert "async_fetch" in tools

    def test_async_fetch_params(self, tools):
        params = {p.name: p for p in tools["async_fetch"].parameters}
        assert "url" in params
        assert "timeout" in params

    def test_async_fetch_url_required(self, tools):
        params = {p.name: p for p in tools["async_fetch"].parameters}
        assert params["url"].required is True

    def test_async_fetch_timeout_default(self, tools):
        params = {p.name: p for p in tools["async_fetch"].parameters}
        assert params["timeout"].default == 30


# ---------------------------------------------------------------------------
# 1d: Nested Click groups
# ---------------------------------------------------------------------------

class TestNestedGroups:
    def test_migrate_discovered(self, tools):
        """Commands in sub-groups should still be scraped."""
        assert "migrate" in tools

    def test_reset_discovered(self, tools):
        assert "reset" in tools

    def test_migrate_subcommand_path(self, tools):
        """migrate is under db which is under cli → path = ['db', 'migrate']."""
        migrate = tools["migrate"]
        assert migrate.subcommand_path is not None
        assert migrate.subcommand_path == ["db", "migrate"], (
            f"Expected ['db', 'migrate'], got {migrate.subcommand_path}"
        )

    def test_reset_subcommand_path(self, tools):
        reset = tools["reset"]
        assert reset.subcommand_path is not None
        assert reset.subcommand_path == ["db", "reset"]

    def test_train_single_level_path(self, tools):
        """Direct children of cli have a single-element path."""
        train = tools["train"]
        assert train.subcommand_path is not None
        assert train.subcommand_path == ["train"]


# ---------------------------------------------------------------------------
# 1e: Hidden options
# ---------------------------------------------------------------------------

class TestHiddenOptions:
    def test_deploy_name_visible(self, tools):
        """Non-hidden params should still be in the tool."""
        assert "deploy" in tools
        params = {p.name: p for p in tools["deploy"].parameters}
        assert "name" in params

    def test_deploy_debug_token_hidden(self, tools):
        """hidden=True params should have ParamDef.hidden == True."""
        params = {p.name: p for p in tools["deploy"].parameters}
        assert "debug_token" in params
        assert params["debug_token"].hidden is True

    def test_deploy_internal_flag_hidden(self, tools):
        """help=click.SUPPRESS params should have ParamDef.hidden == True."""
        params = {p.name: p for p in tools["deploy"].parameters}
        assert "internal_flag" in params
        assert params["internal_flag"].hidden is True

    def test_deploy_visible_param_count(self, tools):
        """Only non-hidden params should count toward visible params."""
        visible = [p for p in tools["deploy"].parameters if not p.hidden]
        assert len(visible) == 1  # only 'name'
