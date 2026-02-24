# Contributing

## Development setup

```bash
git clone https://github.com/bcmcpher/cli2mcp.git
cd cli2mcp
pip install -e ".[dev]"
```

## Running tests

```bash
# All tests
pytest

# Single file
pytest tests/test_click_scraper.py

# Single test
pytest tests/test_click_scraper.py::test_greet_tool_params

# With coverage
pytest --cov=src/cli2mcp --cov-report=term-missing
```

## Running the docs locally

Install the docs dependencies and start the MkDocs dev server:

```bash
pip install -e ".[docs]"
mkdocs serve
```

The site is available at `http://127.0.0.1:8000`. Pages reload automatically when you edit source files.

## Project structure

```
cli2mcp/
├── src/cli2mcp/
│   ├── models.py             # ParamDef, ToolDef data classes
│   ├── config.py             # Config loading from pyproject.toml
│   ├── cli.py                # Click CLI (init, generate, list, validate)
│   ├── scrapers/
│   │   ├── base.py           # BaseScraper ABC
│   │   ├── click_scraper.py  # Click AST scraper
│   │   └── argparse_scraper.py  # argparse AST scraper
│   ├── parsers/
│   │   ├── docstring.py      # NumPy docstring parser
│   │   └── type_mapper.py    # AST type → annotation string
│   └── generators/
│       └── mcp_server.py     # Code generator
├── tests/
│   ├── fixtures/             # Sample CLI files used as test inputs
│   ├── test_cli.py
│   ├── test_click_scraper.py
│   ├── test_argparse_scraper.py
│   ├── test_docstring_parser.py
│   └── test_generator.py
└── docs/                     # MkDocs source
```

## Adding a new scraper

1. Create `src/cli2mcp/scrapers/myframework_scraper.py` subclassing `BaseScraper`.
2. Implement `detect(tree)` and `scrape_file(path)`.
3. Add a fixture CLI file to `tests/fixtures/`.
4. Write tests in `tests/test_myframework_scraper.py`.
5. Register the scraper in `cli.py::_collect_tools`.

## Coding conventions

- **AST-only** — scrapers must never `import`, `exec`, or `eval` user code.
- **No new runtime dependencies** — `click` is the only allowed runtime dep. Generator output dependencies (like `mcp`) belong in the user's environment, not here.
- **Tests required** — new scraper patterns need test coverage before merging.

## Filing issues

Please report bugs and feature requests at <https://github.com/bcmcpher/cli2mcp/issues>.
