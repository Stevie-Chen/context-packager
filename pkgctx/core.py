"""
Core logic for Context Packager.

Recursively walks a project directory, respects .gitignore rules,
skips binary/image files, and bundles source code into a structured
Markdown document.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO

import pathspec


# ---------------------------------------------------------------------------
# File-extension → Markdown language-identifier mapping
# ---------------------------------------------------------------------------
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".ps1": "powershell",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".sql": "sql",
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".dockerfile": "dockerfile",
    ".r": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".vim": "vim",
    ".el": "lisp",
    ".clj": "clojure",
    ".dart": "dart",
    ".tf": "hcl",
    ".proto": "protobuf",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".cmake": "cmake",
    ".make": "makefile",
    ".mk": "makefile",
}

# Files matched by *name* (case-insensitive) that map to a language
FILENAME_LANGUAGE_MAP: dict[str, str] = {
    "makefile": "makefile",
    "dockerfile": "dockerfile",
    "cmakelists.txt": "cmake",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "vagrantfile": "ruby",
    ".gitignore": "gitignore",
    ".dockerignore": "gitignore",
    ".env": "bash",
}

# Binary / non-text extensions to always skip
BINARY_EXTENSIONS: frozenset[str] = frozenset({
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".tiff", ".tif", ".psd", ".ai", ".eps",
    # Audio / Video
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".ogg",
    ".webm", ".m4a", ".m4v",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    # Compiled / binary
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".lib", ".class",
    ".pyc", ".pyo", ".wasm",
    # Documents (binary)
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Database
    ".db", ".sqlite", ".sqlite3",
    # Misc binary
    ".bin", ".dat", ".iso", ".img",
})

# Directories to always skip regardless of .gitignore
ALWAYS_SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    ".DS_Store",
})


# ---------------------------------------------------------------------------
# Gitignore loading
# ---------------------------------------------------------------------------

def load_gitignore(project_root: Path) -> pathspec.PathSpec | None:
    """Load and parse the .gitignore file at *project_root*.

    Returns a compiled ``PathSpec`` matcher, or ``None`` when no
    ``.gitignore`` is present.
    """
    gitignore_path = project_root / ".gitignore"
    if not gitignore_path.is_file():
        return None

    with open(gitignore_path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    return pathspec.PathSpec.from_lines("gitignore", lines)


# ---------------------------------------------------------------------------
# File classification helpers
# ---------------------------------------------------------------------------

def is_binary(filepath: Path) -> bool:
    """Return ``True`` if *filepath* looks like a binary file.

    The check is twofold:
    1. Known binary extensions are rejected immediately.
    2. A small chunk of the file is read and scanned for null bytes.
    """
    if filepath.suffix.lower() in BINARY_EXTENSIONS:
        return True

    try:
        with open(filepath, "rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" in chunk
    except (OSError, IOError):
        return True  # if we can't read it, treat as binary


def detect_language(filepath: Path) -> str:
    """Return the Markdown fence language identifier for *filepath*."""
    name_lower = filepath.name.lower()
    if name_lower in FILENAME_LANGUAGE_MAP:
        return FILENAME_LANGUAGE_MAP[name_lower]

    ext = filepath.suffix.lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, "")


# ---------------------------------------------------------------------------
# Directory walking & collection
# ---------------------------------------------------------------------------

def collect_files(
    project_root: Path,
    gitignore_spec: pathspec.PathSpec | None = None,
) -> list[Path]:
    """Recursively collect non-binary, non-ignored files under *project_root*.

    Files are returned sorted by their path relative to *project_root* for
    deterministic output.
    """
    collected: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(project_root):
        current = Path(dirpath)
        rel_dir = current.relative_to(project_root)

        # Prune always-skip directories (in-place edit of dirnames)
        dirnames[:] = [
            d for d in dirnames
            if d not in ALWAYS_SKIP_DIRS
        ]

        # Prune gitignore-matched directories
        if gitignore_spec is not None:
            dirnames[:] = [
                d for d in dirnames
                if not gitignore_spec.match_file(str(rel_dir / d) + "/")
            ]

        for fname in filenames:
            filepath = current / fname
            rel_path = filepath.relative_to(project_root)

            # Skip gitignore-matched files
            if gitignore_spec is not None and gitignore_spec.match_file(
                str(rel_path)
            ):
                continue

            # Skip binary files
            if is_binary(filepath):
                continue

            collected.append(rel_path)

    collected.sort()
    return collected


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _read_file_text(project_root: Path, rel_path: Path) -> str:
    """Read *rel_path* relative to *project_root* as UTF-8 text.

    Falls back to latin-1 on decode errors so we never crash on oddly
    encoded source files.
    """
    full = project_root / rel_path
    try:
        return full.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return full.read_text(encoding="latin-1")


def generate_markdown(
    project_root: Path,
    files: list[Path],
    out: IO[str],
) -> None:
    """Write a beautifully structured Markdown document to *out*.

    Each file gets a ``## filename`` header followed by a fenced code block
    with the appropriate syntax-highlight language tag.
    """
    project_name = project_root.resolve().name

    # Document header
    out.write(f"# 📦 Context: {project_name}\n\n")
    out.write(f"> Auto-generated by **Context Packager** (`pkgctx`).\n")
    out.write(f"> Source root: `{project_root.resolve()}`\n\n")
    out.write("---\n\n")

    # Table of contents
    out.write("## 📑 Table of Contents\n\n")
    for idx, rel_path in enumerate(files, start=1):
        # GitHub-flavoured Markdown anchor: lowercase, replace non-alphanum
        anchor = str(rel_path).lower().replace("/", "").replace(".", "").replace("_", "").replace("-", "")
        out.write(f"{idx}. [`{rel_path}`](#{anchor})\n")
    out.write("\n---\n\n")

    # File sections
    for rel_path in files:
        lang = detect_language(project_root / rel_path)
        content = _read_file_text(project_root, rel_path)

        out.write(f"## `{rel_path}`\n\n")
        out.write(f"```{lang}\n")
        # Ensure the content ends with a newline before closing the fence
        if content and not content.endswith("\n"):
            content += "\n"
        out.write(content)
        out.write("```\n\n")

    # Footer
    out.write("---\n\n")
    out.write(f"*{len(files)} file(s) packaged.*\n")


def package_context(
    project_root: str | Path,
    output_path: str | Path,
) -> int:
    """High-level entry point: scan *project_root* and write to *output_path*.

    Returns the number of files packaged.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    spec = load_gitignore(root)
    files = collect_files(root, spec)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as fh:
        generate_markdown(root, files, fh)

    return len(files)
