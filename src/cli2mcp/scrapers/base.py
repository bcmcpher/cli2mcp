"""Abstract base class for CLI framework scrapers."""
from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from pathlib import Path

from cli2mcp.models import ToolDef


class BaseScraper(ABC):
    """Base class for scrapers that extract ToolDef objects from Python source files."""

    @abstractmethod
    def scrape_file(self, path: Path) -> list[ToolDef]:
        """Parse a Python source file and return all discovered CLI tools."""
        ...

    @abstractmethod
    def detect(self, tree: ast.AST) -> bool:
        """Return True if this file uses the framework this scraper handles."""
        ...
