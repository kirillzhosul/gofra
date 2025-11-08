# Preprocessor

Preprocessor is an stage in within compilation (simplified) that works with lexer tokens (e.g raw text) and resolves references to preprocessor itself (e.g `#include` is preprocessor only directive and will throw an error if occurred at next possible stage: parser)

All preprocessor keywords begins with `#`

## Include system and `#include`
Most of the time you do not write program in a single file, or require additional code from libraries, in Gofra `#include` allows to straightforward include whole text of an file (with some additional file path resolving and include-once strategy)

```gofra

#include "sum.gof"

func void main
    2 2 sum // sum is defined at sum.gof
end
```

Include system is like *recursive* so all definitions of an preprocessor will be available at include side

### Module include
In Gofra, there is convention that when you include an directory (e.g `#include "dir"`) it will search for file in that directory named same as directory itself, e.g `dir` directory will search for `dir/dir.gof` file and that is being included, that simplifies layout of directory tree of libraries

### Searching strategy

At start of search, same file or an directory (e.g directory include file) will be searched in current working file directory parent, e.g if you include something from stdlib and it include something it first looks at its own directory, not your main one
At next, if file is not found, it will search from directory where you main file is located
And if file is not found there also, it will search against all include search directory (e.g `-isd` CLI flag)

Overview:
1. Parent of an current file (not main)
2. Parent of an main file
3. Include search directories

## Macro definitions

To define an macro you can use `#define` preprocessor directive (and `#undef`) correspondingly

```gofra
#define MACRO 2 // macro containing an token 2
```

after that you are allowed to inject that macro inside your code

```gofra
MACRO MACRO + // 4 (2 2 +)
```

### Propagation via CLI
You can use `-D` flag to define an macro from CLI which is useful for something like debug flags
`-Ddebug=1` (define an macro `debug` with value 1)

### Definition checking at preprocessor stage
You can use `#ifdef`, `#ifndef` and `#endif` for checking definition of an macro
```gofra
#idedef DEBUG
    // only be compiled if DEBUG macro is present
#endif
```

### Toolchain propagated macros and target specific macros
By default Gofra provides two macros: `OS_{NAME}` and `ARCH_{NAME}`
For example while compiling to Darwin on ARM64 there will be 2 macros available -> `OS_DARWIN` and `ARCH_ARM64`