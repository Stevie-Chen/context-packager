# Context Packager (pkgctx)

A highly efficient custom Python CLI tool that recursively traverses a local project directory, respects standard `.gitignore` files, automatically filters out heavy background modules/binary files, and bundles your entire codebase context into a single structured Markdown file. 

Perfect for instantly feeding clean codebase maps directly into AI prompts (like Gemini or Claude).

## Key Features
- **Smart Traversing:** Respects local patterns dynamically using `pathspec`.
- **Safety First:** Automatically skips binaries, images, lockfiles, and node extensions via a null-byte heuristic filter.
- **AI-Optimized Output:** Automatically builds a Table of Contents (TOC) mapping your repository followed by syntax-highlighted code blocks.

##  Requirements & Installation
Ensure you have Python 3.12+ installed on your Mac.

```bash
# Clone the repository
git clone https://github.com
cd context-packager

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
Run the script module layout directly:
```bash
python -m pkgctx [TARGET_DIRECTORY] -o [OUTPUT_FILE.md]
```

**Example:**
```bash
python -m pkgctx . -o my_codebase_context.md
```
