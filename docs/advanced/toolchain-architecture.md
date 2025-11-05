# Toolchain (Compiler) architecture

This page explains internals of compiler (toolchain) and is useful for development, continue reading if you need this

## Core modules

Toolchain consists of widely used components: Lexer, Parser, Codegen but also contains Preprocessor, Optimizer, Typechecker and also relatable to notice is Linker, Assembler and CLI


## Toolchain CLI goal flow


`CLI -> Lexer -> Preprocessor -> Parser -> Typechecker -> Optimizer -> Codegen -> Assembler -> Linker`


## Structure of default Code-generators

By default all architectures emits assembly-code (e.g almost nearly machine code) that is requires to be assembler into binary machine code via Assembler


## Structure of typechecker

As parser produce an HIR and does barely perform type checking, there is an Typechecker module which is responsible for checking that types are compatible within operations (e.g plus or function call)