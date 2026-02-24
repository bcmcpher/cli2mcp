# Scrapers

AST-based scrapers that extract CLI metadata from Python source files without importing them.

## `BaseScraper`

::: cli2mcp.scrapers.base.BaseScraper
    options:
      show_source: true

---

Abstract base class for all scrapers. Subclasses must implement `detect()` and `scrape_file()`.

---

## `ClickScraper`

::: cli2mcp.scrapers.click_scraper.ClickScraper
    options:
      show_source: true
      members:
        - __init__
        - detect
        - scrape_file

Recognises Click CLI files by detecting `import click` or `from click import ...` in the AST. Extracts every function decorated with `@click.command()` or `@group.command()`.

**Supported patterns:**

- `@click.argument()` — positional parameters
- `@click.option()` — optional parameters, flags, multiple options
- `@click.option(type=click.Choice([...]))` — enumerated choices
- `@click.group()` / `@group.command()` — command groups

---

## `ArgparseScraper`

::: cli2mcp.scrapers.argparse_scraper.ArgparseScraper
    options:
      show_source: true
      members:
        - __init__
        - detect
        - scrape_file

Recognises argparse CLI files by detecting `import argparse` or `from argparse import ...`. Extracts every function that creates an `ArgumentParser` and calls `add_argument()`.

**Supported patterns:**

- Positional arguments (required by default)
- `--option` flags with `type=`, `default=`, `required=`, `help=`
- `action="store_true"` / `action="store_false"` — boolean flags
- `action="append"` — list-valued options
- `nargs="+"` / `nargs="*"` / `nargs=N` — multi-value options
- `choices=[...]` — enumerated values
- `add_subparsers()` / `add_parser()` — subcommand patterns
- `prog=` on `ArgumentParser` — sets the CLI subcommand name
- `dest=` — destination variable name (dashes sanitised to underscores)
