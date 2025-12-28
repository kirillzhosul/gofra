"""Assembler package that translated *assembly* file into *object* file.

For example in codegen that is not emitting final object file, we need to call an *assembler* that is translates our codegen result
(e.g an `.s` assembly file with text machine instructions) into object file that is suitable for next possible linkage (linker) step

For example in x86_64 (AMD64) toolchain target workflow is:
- Gofra high-level toolchain (Lex -> parse IR (HIR))
- Pass that into Gofra codegen which may translate that HIR into LIR for internal code generation and translate that into an assembly file
- We need to translate that assembly into an object file via that assembler tooling
- [after emitting an object file we link it into final binary (e.g executable for most cases)]
In matchup: Lexer (Tokens) -> Parser (HIR) -> Codegen (Assembly Text) -> Assembler (Object file) -> Linker (Binary)

This is not required for targets / codegen that emits final *object* file (e.g any codegen that emits binary machine instructions in form of an object file)

(Not exist in toolchain, only reference):
In LLVM partial (llvm only as LIR) workflow  we still receive LLVM IR (LIR) that needs translation to binary object file
In LLVM full workflow we use `clang` to fully compile source file (codegen assembly -> executable) but this hides abstraction (which is mostly not used by language toolchain, but anyway)
"""

from .assembler import assemble_object_file

__all__ = ["assemble_object_file"]
