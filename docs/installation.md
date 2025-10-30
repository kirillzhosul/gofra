# Installation

## Pre requirements

Gofra is a Python-based toolchain, so you only require a Python installation. However, as a toolchain-compiled code, it depends on the target-specific linker and assembler.

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

(Step 2): Verify installation
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

(It will also propagate the local `gofra` command over the system-wide gofra if you are inside the environment (e.g. `poetry shell`))

