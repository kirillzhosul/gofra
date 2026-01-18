/*
    Example loader script for Node.js and Gofra WASM (includes required ENV)
*/

const fs = require('fs');
const path = 'test.wasm'
const bytes = new Uint8Array(fs.readFileSync(path));

const memory = new WebAssembly.Memory({ initial: 1 });


const getStringFromStringViewPtr = (ptr) => {
    const view = new DataView(memory.buffer);
    const offset = Number(ptr);

    const stringRawPtr = view.getBigInt64(offset, true);
    const length = view.getBigInt64(offset + 8, true);

    const stringBytes = new Uint8Array(memory.buffer, Number(stringRawPtr), Number(length));
    const text = new TextDecoder().decode(stringBytes);
    return text
}

const wasm32_print_fd = (fd, ptr) => {
    const text = getStringFromStringViewPtr(ptr)


    if (fd === 1n) {
        process.stdout.write(text)
    } else if (fd === 2n) {
        console.error(text);
    } else {
        console.error("Unknown FD " + fd)
        return BigInt(0);
    }

    return BigInt(text.length);
}

const importObject = {
    env: {
        wasm32_print_fd,
        memory,
    }
};


WebAssembly.instantiate(bytes, importObject).then(obj => {
    const _exports = obj.instance.exports;
    _exports.main()
}).catch(err => {
    console.error('Failed to instantiate WASM:', err);
});