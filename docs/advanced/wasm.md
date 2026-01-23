# WebAssembly (WASM)

This page covers essentials and underlying tech required for working with *Gofra* as compiler for [*WASM*](https://webassembly.org/) target.

## What is WASM?

*WASM* is an alternative for writing web-based (browser) applications, it offers near-native performance, and compilation from high-level languages like *Gofra* to it machine instructions

Any file with `.wasm` extension is machine instructions code that must be loaded via appropriate environment (Node.js/Browser)

Any file with `.wat` extension is assembly textual representation of WASM

## Compiling `"Hello, World!"` to WASM

To compile something simple like `"Hello, World!"` you need to specify target like `--target wasm`/`-t wasm`

As WASM isn't executable on its own it requires appropriate environment, so we specify `-of object` to emit `.wasm` file (WASM target does not allows to emit default `-of executable` target)

After these steps we have command like `gofra ./hello_world.gof -t wasm -of object` which emits `hello_world.wasm` to us.

## How to execute WASM artifact

To execute almost any WASM artifact (e.g `.wasm` file) you need loader with environment, one of those is *Node.JS*, loader for it located in `/wasm/node_example_loader.js`, same logic and environment is usable for browsers with tweaking how loader *loads* wasm file and from which script (e.g `.html`)

For more complex examples with environment look into `/wasm/example_wasm_raylib_layer_loader.html`