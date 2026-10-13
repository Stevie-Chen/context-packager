"""
Command-line interface for Context Packager.

Usage:
    pkgctx <directory> [-o output.md]
    python -m pkgctx <directory> [-o output.md]
"""

from __future__ import annotations

from pathlib import Path

import click

from pkgctx.core import package_context


@click.command(
    name="pkgctx",
    help=(
        "📦 Context Packager — bundle a project's source code into a single, "
        "beautifully structured Markdown file.\n\n"
        "Scans DIRECTORY recursively, respects .gitignore rules, skips "
        "binary/image files, and writes syntax-highlighted code blocks "
        "to the output file."
    ),
)
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.option(
    "-o",
    "--output",
    default="context.md",
    show_default=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Output Markdown file path.",
)
@click.version_option(version="0.1.0", prog_name="pkgctx")
def cli(directory: str, output: str) -> None:
    """Entry point for the pkgctx CLI."""
    dir_path = Path(directory)
    out_path = Path(output)

    click.echo(f"📦 Scanning: {dir_path}")
    click.echo(f"📝 Output:   {out_path}")
    click.echo()

    try:
        count = package_context(dir_path, out_path)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"✅ Done! {count} file(s) packaged into {out_path}")


def main() -> None:
    """Wrapper so entry_points / __main__ can call a plain function."""
    cli()
