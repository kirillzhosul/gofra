# Installation

## Prerequirements

Gofra is an Python-based toolchain so you must only required to have Python installation.
But as toolchain compiled code, it depends on target-specific linker and assembler.

- [Python >3.12.x](https://www.python.org) available as `python` or `python3` command
- GNU/Mach-O Linker (ld) - For linking compiled objects
- Assembler (as) - Typically included with Clang LLVM compiler

[Gofra](https://github.com/kirillzhosul/gofra) is distributed as single Python-based toolchain. To install:

## Install

(Step 1): Install toolchain
```bash
pip install gofra
```

(Step 2): Verify Installation
```bash
gofra --help
```


## Development installation

(Step 1): Clone the repository
```bash
git clone https://github.com/kirillzhosul/gofra.git
cd gofra
```

(Step 2): Verify Installation
```bash
cd gofra
python -m gofra --help
```
(Step 3): Install dependencies ([Poetry](https://python-poetry.org) required)
```bash
# In repository root
poetry install --with dev,docs
```

This will install [Ruff](https://astral.sh/ruff) and [MkDocs](https://www.mkdocs.org) available as:
```bash
# Serve documentation
mkdocs serve
# Lint source code
ruff .
```

(It will also propagate local `gofra` command over system-wide gofra if you inside environment (e.g `poetry shell`))

