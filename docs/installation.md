# Installation

## Prerequirements

Gofra is an Python-based toolchain so you must only required to have Python installation.
But as toolchain compiled code, it depends on target-specific linker and assembler.

- [Python >3.12.x](https://www.python.org) available as `python` or `python3` command
- GNU/Mach-O Linker (ld) - For linking compiled objects
- Assembler (as) - Typically included with Clang LLVM compiler

[Gofra](https://github.com/kirillzhosul/gofra) is distributed as single Python-based toolchain. To install:

## Install from sources

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
(Step 3): Try an example (Optional)
```bash
# More examples available in `./examples`
python -m gofra examples/01_hello_world.gof
```

## System wide insallation
Currently, system wide installation is not yet supported but you may add an alias to `scripts/entrypoint-alias.py`.
(It has no dependencies so it will run without environment) consider naming it `gofra` (as it will not detect real alias name to give proper executable path)

## Development installation

If you wish to maintain development for toolchain initial steps will be same but you also need development tools, which is installed using [Poetry](https://python-poetry.org) (install before running command below)

```bash
# In repository root
poetry install --with dev,docs
```

This will install [Ruff]() and [MkDocs]() available as:
```bash
# Serve documentation
mkdocs serve
# Lint source code
ruff .
```

(It will also propagate environment local `gofra-cli` script as alias to `python -m gofra`)

