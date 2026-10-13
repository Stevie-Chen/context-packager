"""
Tests for Context Packager (pkgctx).

Covers:
- .gitignore loading and filtering
- Binary file detection
- Language detection from extensions/filenames
- Markdown generation structure and content
- End-to-end package_context integration
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pkgctx.core import (
    collect_files,
    detect_language,
    generate_markdown,
    is_binary,
    load_gitignore,
    package_context,
)


# ===================================================================
# Helpers
# ===================================================================


def _create_file(path: Path, content: str = "") -> None:
    """Create a file (and parent dirs) with the given text content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_binary_file(path: Path) -> None:
    """Create a file containing null bytes (binary-like)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x01\x02\x03binary content")


# ===================================================================
# .gitignore loading
# ===================================================================


class TestLoadGitignore:
    def test_returns_none_when_no_gitignore(self, tmp_path: Path) -> None:
        """No .gitignore → returns None."""
        assert load_gitignore(tmp_path) is None

    def test_returns_pathspec_when_gitignore_exists(self, tmp_path: Path) -> None:
        """A valid .gitignore → returns a PathSpec instance."""
        _create_file(tmp_path / ".gitignore", "*.log\nbuild/\n")
        spec = load_gitignore(tmp_path)
        assert spec is not None

    def test_parsed_patterns_match(self, tmp_path: Path) -> None:
        """.gitignore patterns should match expected paths."""
        _create_file(tmp_path / ".gitignore", "*.log\nbuild/\n__pycache__/\n")
        spec = load_gitignore(tmp_path)

        assert spec.match_file("debug.log")
        assert spec.match_file("nested/error.log")
        assert spec.match_file("build/")
        assert not spec.match_file("main.py")
        assert not spec.match_file("src/app.js")


# ===================================================================
# Binary file detection
# ===================================================================


class TestIsBinary:
    def test_known_binary_extension(self, tmp_path: Path) -> None:
        """Files with binary extensions are detected without reading."""
        img = tmp_path / "photo.png"
        _create_file(img, "not really a png")
        assert is_binary(img) is True

    def test_text_file_not_binary(self, tmp_path: Path) -> None:
        """Regular text files are not flagged as binary."""
        txt = tmp_path / "readme.md"
        _create_file(txt, "# Hello World\n")
        assert is_binary(txt) is False

    def test_null_bytes_detected(self, tmp_path: Path) -> None:
        """Files containing null bytes are flagged as binary."""
        binfile = tmp_path / "data.custom"
        _create_binary_file(binfile)
        assert is_binary(binfile) is True

    def test_unreadable_file_treated_as_binary(self, tmp_path: Path) -> None:
        """If a file can't be read, treat it as binary."""
        fake = tmp_path / "nonexistent.xyz"
        # Don't create it — is_binary should return True
        assert is_binary(fake) is True

    @pytest.mark.parametrize("ext", [".exe", ".jpg", ".mp3", ".zip", ".pyc", ".wasm"])
    def test_various_binary_extensions(self, tmp_path: Path, ext: str) -> None:
        f = tmp_path / f"file{ext}"
        _create_file(f, "placeholder")
        assert is_binary(f) is True


# ===================================================================
# Language detection
# ===================================================================


class TestDetectLanguage:
    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("main.py", "python"),
            ("index.js", "javascript"),
            ("App.tsx", "typescript"),
            ("server.go", "go"),
            ("lib.rs", "rust"),
            ("style.css", "css"),
            ("data.json", "json"),
            ("config.yaml", "yaml"),
            ("script.sh", "bash"),
        ],
    )
    def test_extension_mapping(self, filename: str, expected: str) -> None:
        assert detect_language(Path(filename)) == expected

    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("Makefile", "makefile"),
            ("Dockerfile", "dockerfile"),
            ("Gemfile", "ruby"),
            (".gitignore", "gitignore"),
            (".env", "bash"),
        ],
    )
    def test_filename_mapping(self, filename: str, expected: str) -> None:
        assert detect_language(Path(filename)) == expected

    def test_unknown_extension_returns_empty(self) -> None:
        assert detect_language(Path("data.unknown_ext_xyz")) == ""


# ===================================================================
# File collection with .gitignore
# ===================================================================


class TestCollectFiles:
    def test_collects_text_files(self, tmp_path: Path) -> None:
        """Basic text files are collected."""
        _create_file(tmp_path / "main.py", "print('hi')")
        _create_file(tmp_path / "readme.md", "# Hi")

        files = collect_files(tmp_path)
        names = [str(f) for f in files]

        assert "main.py" in names
        assert "readme.md" in names

    def test_skips_binary_files(self, tmp_path: Path) -> None:
        """Binary files are excluded."""
        _create_file(tmp_path / "app.py", "x = 1")
        _create_file(tmp_path / "logo.png", "fake png")

        files = collect_files(tmp_path)
        names = [str(f) for f in files]

        assert "app.py" in names
        assert "logo.png" not in names

    def test_skips_always_skip_dirs(self, tmp_path: Path) -> None:
        """Directories like .git, __pycache__, node_modules are skipped."""
        _create_file(tmp_path / ".git" / "config", "git config")
        _create_file(tmp_path / "__pycache__" / "mod.cpython-312.pyc", "bytecode")
        _create_file(tmp_path / "node_modules" / "pkg" / "index.js", "module.exports = {}")
        _create_file(tmp_path / "src" / "app.py", "print('hello')")

        files = collect_files(tmp_path)
        names = [str(f) for f in files]

        assert "src/app.py" in names
        assert not any(".git" in n for n in names)
        assert not any("__pycache__" in n for n in names)
        assert not any("node_modules" in n for n in names)

    def test_respects_gitignore_file_patterns(self, tmp_path: Path) -> None:
        """.gitignore file patterns filter out matching files."""
        _create_file(tmp_path / ".gitignore", "*.log\n*.tmp\nsecrets.env\n")
        _create_file(tmp_path / "app.py", "code")
        _create_file(tmp_path / "debug.log", "log data")
        _create_file(tmp_path / "cache.tmp", "temp data")
        _create_file(tmp_path / "secrets.env", "SECRET=abc")

        spec = load_gitignore(tmp_path)
        files = collect_files(tmp_path, spec)
        names = [str(f) for f in files]

        assert "app.py" in names
        # .gitignore itself should be collected (it's not ignored)
        assert ".gitignore" in names
        assert "debug.log" not in names
        assert "cache.tmp" not in names
        assert "secrets.env" not in names

    def test_respects_gitignore_directory_patterns(self, tmp_path: Path) -> None:
        """.gitignore directory patterns filter out entire directories."""
        _create_file(tmp_path / ".gitignore", "dist/\ncoverage/\n")
        _create_file(tmp_path / "src" / "main.py", "code")
        _create_file(tmp_path / "dist" / "bundle.js", "bundled")
        _create_file(tmp_path / "coverage" / "report.html", "<html>")

        spec = load_gitignore(tmp_path)
        files = collect_files(tmp_path, spec)
        names = [str(f) for f in files]

        assert "src/main.py" in names
        assert not any("dist" in n for n in names)
        assert not any("coverage" in n for n in names)

    def test_results_are_sorted(self, tmp_path: Path) -> None:
        """Collected files are sorted alphabetically by relative path."""
        _create_file(tmp_path / "z.py", "")
        _create_file(tmp_path / "a.py", "")
        _create_file(tmp_path / "m" / "b.py", "")

        files = collect_files(tmp_path)
        assert files == sorted(files)

    def test_nested_files_collected(self, tmp_path: Path) -> None:
        """Files in nested subdirectories are collected."""
        _create_file(tmp_path / "a" / "b" / "c" / "deep.py", "deep")

        files = collect_files(tmp_path)
        names = [str(f) for f in files]
        assert "a/b/c/deep.py" in names


# ===================================================================
# Markdown generation
# ===================================================================


class TestGenerateMarkdown:
    def _generate(self, tmp_path: Path, files: list[Path]) -> str:
        """Helper: generate markdown into a string buffer."""
        buf = io.StringIO()
        generate_markdown(tmp_path, files, buf)
        return buf.getvalue()

    def test_header_contains_project_name(self, tmp_path: Path) -> None:
        md = self._generate(tmp_path, [])
        assert f"# 📦 Context: {tmp_path.resolve().name}" in md

    def test_header_contains_auto_generated_note(self, tmp_path: Path) -> None:
        md = self._generate(tmp_path, [])
        assert "Auto-generated by **Context Packager**" in md

    def test_toc_lists_all_files(self, tmp_path: Path) -> None:
        _create_file(tmp_path / "foo.py", "x = 1")
        _create_file(tmp_path / "bar.js", "let x = 1;")
        files = [Path("bar.js"), Path("foo.py")]

        md = self._generate(tmp_path, files)
        assert "`bar.js`" in md
        assert "`foo.py`" in md

    def test_code_blocks_have_correct_language(self, tmp_path: Path) -> None:
        _create_file(tmp_path / "app.py", "print('hi')")
        files = [Path("app.py")]

        md = self._generate(tmp_path, files)
        assert "```python" in md

    def test_file_content_included(self, tmp_path: Path) -> None:
        _create_file(tmp_path / "hello.py", "print('hello world')")
        files = [Path("hello.py")]

        md = self._generate(tmp_path, files)
        assert "print('hello world')" in md

    def test_footer_file_count(self, tmp_path: Path) -> None:
        _create_file(tmp_path / "a.py", "")
        _create_file(tmp_path / "b.py", "")
        files = [Path("a.py"), Path("b.py")]

        md = self._generate(tmp_path, files)
        assert "2 file(s) packaged" in md

    def test_empty_project_produces_valid_markdown(self, tmp_path: Path) -> None:
        md = self._generate(tmp_path, [])
        assert "0 file(s) packaged" in md
        assert "## 📑 Table of Contents" in md


# ===================================================================
# End-to-end integration
# ===================================================================


class TestPackageContextIntegration:
    def test_end_to_end(self, tmp_path: Path) -> None:
        """Full pipeline: create files, package, verify output."""
        project = tmp_path / "myproject"
        project.mkdir()

        _create_file(project / "main.py", "if __name__ == '__main__':\n    pass\n")
        _create_file(project / "utils.py", "def helper():\n    return 42\n")
        _create_file(project / "README.md", "# My Project\n")
        _create_file(project / ".gitignore", "*.pyc\ndist/\n")
        _create_file(project / "dist" / "out.js", "compiled")
        _create_file(project / "cache.pyc", "bytecode")

        output = tmp_path / "output.md"
        count = package_context(project, output)

        assert output.exists()
        content = output.read_text(encoding="utf-8")

        # Correct files included
        assert count == 4  # main.py, utils.py, README.md, .gitignore
        assert "main.py" in content
        assert "utils.py" in content
        assert "README.md" in content
        assert ".gitignore" in content

        # Gitignored files excluded
        assert "dist/out.js" not in content
        assert "cache.pyc" not in content

        # Syntax highlighting
        assert "```python" in content
        assert "```markdown" in content
        assert "```gitignore" in content

        # Content present
        assert "def helper():" in content
        assert "# My Project" in content

    def test_nonexistent_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            package_context(tmp_path / "nope", tmp_path / "out.md")
