/*
    Example loader script for Node.js and Gofra WASM (includes required ENV)
*/


// Change this
const WASM_ARTIFACT_PATH = 'test.wasm'

import { readFileSync } from 'fs';
const bytes = new Uint8Array(readFileSync(WASM_ARTIFACT_PATH));

const memory = new WebAssembly.Memory({ initial: 1 });
const getGofraWasmRuntime = (memory) => {
    const _getStringFromStringViewPtr = (ptr) => {
        const view = new DataView(memory.buffer);
        const offset = Number(ptr);

        const stringRawPtr = view.getBigInt64(offset, true);
        const length = view.getBigInt64(offset + 8, true);

        const stringBytes = new Uint8Array(memory.buffer, Number(stringRawPtr), Number(length));
        const text = new TextDecoder().decode(stringBytes);
        return text
    }

    const gofra_print_fd = (fd, ptr) => {
        const text = _getStringFromStringViewPtr(ptr)
        switch (fd) {
            case 1n:
                process.stdout.write(text);
                break;
            case 2n:
                process.stderr.write(text);
                break;
            default:
                console.error("Unknown FD " + fd);
                return BigInt(0);
        }
        return BigInt(text.length);
    }

    return {
        wasm32_print_fd: gofra_print_fd
    }
}
export const gofraGetTextFromCString = (textPtr) => {
    const offset = Number(textPtr);
    const buffer = memory.buffer;

    let length = 0;
    while (true) {
        const byte = new Uint8Array(buffer, offset + length, 1)[0];
        if (byte === 0) break;
        length++;

        // Safety check
        if (length > 10000) {
            console.error("String too long or missing null terminator");
            break;
        }
    }

    // Read the string
    const stringBytes = new Uint8Array(buffer, offset, length);
    const text = new TextDecoder().decode(stringBytes);
    return text;
};

const importObject = {
    env: {
        memory,
        ...getGofraWasmRuntime(memory),
    }
};

WebAssembly.instantiate(bytes, importObject).then(obj => {
    const _exports = obj.instance.exports;
    _exports.main()
}).catch(err => {
    console.error('Failed to instantiate WASM:', err);
});