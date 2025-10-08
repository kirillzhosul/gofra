# Gofra Linker (gofra-ld)

Gofra Linker is a cross-platform tool that links multiple object files and libraries to produce output in various formats including executables, shared libraries, and static objects. 
It serves as a unified interface to underlying system linkers while providing consistent behavior across different platforms.

## Installation

Gofra Linker is distributed as part of the Gofra toolchain and is available system-wide as `gofra-ld`after installation.

## Linker backends

Gofra Linker is uses what is called *backend* under the hood - after selecting appropriate backend it composes proper linker command and executes it.
At current moment there is only 2 backends: `gnu-ld` and `apple-ld` (shares almost same philosophy and interface)
By default backend is inferred by host machine and target but can be overridden by passing `--linker-backend` argument to the CLI.