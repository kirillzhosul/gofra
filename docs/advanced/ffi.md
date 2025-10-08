# FFI (Foreign Function Interface)

Read about FFI at [Wikipedia](https://en.wikipedia.org/wiki/Foreign_function_interface)

This documentation page is written for `AARCH64_MacOS` target and may be irrelevant for some underneath implementations on different targets, like FFI naming conventions on different assemblers

---

Gofra is capable of calling functions that written in other languages and externally defined, for example using libraries written for/in `C` or other language, or using system libraries.

To do that assembler after code generation at linker stage should be acknowledged of external libraries (via CLI linker flags) and Gofra source code should specify which functions being external for FFI.


# `extern` marker

Functions marked with `extern` keyword/marker will be treated as externally defined via FFI for example external function `puts` from `libc` is declared as:
```gofra
extern func int _puts[*char[]]
```

This is written according to `libc` library `C` interface: 
```C
int puts(const char *s){ ... }
```

External functions in Gofra **CANNOT** have any tokens inside otherwise compiler will throw an error

# Type contracts for FFI

To specify which data is expected for and from external function you specify type contract for that functions (like default functions in Gofra)

Every argument will be treated by compiler and will be passed to that function, as well as external function return data will be pushed onto stack for you

# Variadic arguments (type contracts)

For now, there is no way to pass variadic arguments to external function
(Hack or workaround for that is only to create non-variadic wrappers with different number of arguments to pass to underlying external function which type contract is expanded for max required amount of arguments)

# Linker stage

For letting linker know about that dependencies (Libraries with FFI), you can pass `-l` flag(s) to the compiler

For example linking with `raylib` and using their functions:
`-lraylib` (`-L/opt/homebrew/lib` if search directory was not found with pkgconfig (`--no-pkg-config`))
