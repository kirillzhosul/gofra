# Gofra [beta]

**A Stack-based compiled programming language.**

**The project is made not for competing with other languages, rather it is another incomplete language almost same like others.**

## Overview
Gofra is a **concatenative** (stack-based) programming language that compiles to native code. 
Programs are written using [Reverse Polish notation](https://en.wikipedia.org/wiki/Reverse_Polish_notation), where operations follow their operands (e.g `2 + 2` is `2 2 +`).

## Quick start

Here's a simple **"Hello, World!"** example:
```gofra
include "std"

func void main
    "Hello, World!" println
end
```

## Features
- *Native* - Compiles to native machine code
- *C*-like - Close to C, but has a few more high-level abstraction (`for in`, `type generics`)
- *C FFI* - Seamless integration with **C**-FFI libraries
- *Low-level* - Write unsafe, low-level code with direct memory access
- *Type System* - Validate types at compile time, has compile-time warnings (Partial generics supports, typechecker)
- *Library* - By default has support for `math`, `random`, `network` and other libraries
- *First class functions* - Has support, and lambda definitions (no closures/capturing yet)

## Showcase
- Pong Game (`examples/03_pong.gof`)
- Simple HTTP server (`examples/04_http_server.gof`)

## Milestones

## Platform support
Gofra currently supports native compilation (no cross-compilation yet). You must compile on the same platform as your target.

- Full: **AArch64** macOS (Darwin)
- Partial, buggy: **x86_64** (Linux), **WASM**

(Windows **x86_64** is must be supported soon, requires contributors)

## Pre requirements

Before installing Gofra, ensure you have the following tools available system-wide:

- [Python >3.12.x](https://www.python.org)

For `x86_64` / `ARM` targets:
- GNU/Mach-O Linker (ld) - For linking compiled objects
- Assembler (as) - Typically included with Clang LLVM compiler

For `WASM` target:
- - `WABT` toolkit (`wat2wasm`)
## Installation

**For full installation steps, please visit [Installation](./installation.md) page.**

[Gofra](https://github.com/kirillzhosul/gofra) is distributed as single Python-based toolchain. To install:

(Step 1): Install toolchain
```bash
pip install gofra
```
(Step 2): Verify Installation
```bash
gofra --help
```