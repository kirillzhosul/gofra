# Gofra

**A Stack-based compiled programming language**

**Project is made for FUN and educational purposes! Don`t expect anything cool from it and just try/contribute**

---
#### [Documentation and information is available here](https://kirillzhosul.github.io/gofra)
---

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

## Platform support
Gofra currently supports native compilation (no cross-compilation yet). You must compile on the same platform as your target:

- **x86_64** (Linux)
- **AArch64** macOS (Darwin)

## Features
- *Low-level* - Write unsafe, low-level code with direct memory access
- *Native Compilation* - Generates optimized native assembly code
- *Type Safety* - Validates stack usage and type correctness at compile time
- *C FFI* - Seamless integration with **C** libraries (including libc)

## Installation

**For full installation steps, please visit [Documentation](https://kirillzhosul.github.io/gofra) page**

[Gofra](https://github.com/kirillzhosul/gofra) is distributed as single Python-based toolchain. To install:

```bash
pip install gofra
gofra --help
```


## More information and next steps

Please refer to actual [Documentation](https://kirillzhosul.github.io/gofra)!