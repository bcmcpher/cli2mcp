"""Load [tool.cli2mcp] configuration from pyproject.toml."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError as exc:
            raise ImportError(
                "Python < 3.11 requires the 'tomli' package: pip install tomli"
            ) from exc


@dataclass
class Config:
    server_name: str
    entry_point: str
    source_dirs: list[Path]
    output_file: Path = field(default_factory=lambda: Path("mcp/mcp_tools_generated.py"))
    server_file: Path = field(default_factory=lambda: Path("mcp/mcp_server.py"))
    include_patterns: list[str] = field(default_factory=lambda: ["*.py"])
    exclude_patterns: list[str] = field(default_factory=lambda: ["test_*", "_*"])
    subprocess_timeout: int | None = None


def load_config(config_path: Path) -> Config:
    """Load and validate [tool.cli2mcp] from a pyproject.toml file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("rb") as f:
        data = tomllib.load(f)

    section = data.get("tool", {}).get("cli2mcp", {})

    if not section:
        raise ValueError(
            f"No [tool.cli2mcp] section found in {config_path}"
        )

    server_name = section.get("server_name")
    if not server_name:
        raise ValueError("'server_name' is required in [tool.cli2mcp]")

    entry_point = section.get("entry_point")
    if not entry_point:
        raise ValueError("'entry_point' is required in [tool.cli2mcp]")

    raw_source_dirs = section.get("source_dirs")
    if not raw_source_dirs:
        raise ValueError("'source_dirs' is required in [tool.cli2mcp]")

    config_dir = config_path.parent
    source_dirs = [config_dir / d for d in raw_source_dirs]

    output_file_raw = section.get("output_file", "mcp/mcp_tools_generated.py")
    output_file = config_dir / output_file_raw

    server_file_raw = section.get("server_file", "mcp/mcp_server.py")
    server_file = config_dir / server_file_raw

    include_patterns = section.get("include_patterns", ["*.py"])
    exclude_patterns = section.get("exclude_patterns", ["test_*", "_*"])
    subprocess_timeout = section.get("subprocess_timeout", None)

    return Config(
        server_name=server_name,
        entry_point=entry_point,
        source_dirs=source_dirs,
        output_file=output_file,
        server_file=server_file,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        subprocess_timeout=subprocess_timeout,
    )
