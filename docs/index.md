# Gofra

**A Stack-based compiled programming language**

## Overview
Gofra is a **concatenative** (stack-based) programming language that compiles to native code. 
Programs are written using [Reverse Polish notation](https://en.wikipedia.org/wiki/Reverse_Polish_notation), where operations follow their operands (e.g `2 + 2` is `2 2 +`).

## Quick start

Here's a simple **"Hello, World!"** example:
```gofra
include "std.gof"

func void main
    FD_STD_OUT "Hello, World!\n" sc_write drop
end
```

## Features
- *Low-level* - Write unsafe, low-level code with direct memory access
- *Native Compilation* - Generates optimized native assembly code
- *Type Safety* - Validates stack usage and type correctness at compile time
- *C FFI* - Seamless integration with **C** libraries (including libc)

## Platform support
Gofra currently supports native compilation (no cross-compilation yet). You must compile on the same platform as your target:

- **x86_64** (Linux)
- **AArch64** macOS (Darwin)

## Prerequirements

Before installing Gofra, ensure you have the following tools available system-wide:

- [Python >3.12.x](https://www.python.org) available as `python` or `python3` command
- GNU/Mach-O Linker (ld) - For linking compiled objects
- Assembler (as) - Typically included with Clang LLVM compiler

## Installation

**For full installation steps, please visit [Installation](./installation.md) page**

[Gofra](https://github.com/kirillzhosul/gofra) is distributed as single Python-based toolchain. To install:

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

