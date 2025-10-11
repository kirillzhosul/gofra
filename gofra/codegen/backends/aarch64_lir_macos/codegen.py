"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING

from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext
from gofra.codegen.backends.aarch64_macos.assembly import (
    drop_stack_slots,
    push_integer_onto_stack,
    push_static_address_onto_stack,
)
from gofra.codegen.lir import LIRProgram, translate_hir_to_lir
from gofra.codegen.lir.ops import (
    LIRAddRegs,
    LIRBaseOp,
    LIRBitwiseAndRegs,
    LIRBitwiseOrRegs,
    LIRDebuggerTraceTrap,
    LIRDropStackSlot,
    LIRFloorDivRegs,
    LIRFunctionAcquireArguments,
    LIRFunctionCall,
    LIRFunctionCallAcquireRetval,
    LIRFunctionCallPrepareArguments,
    LIRFunctionPrepareRetval,
    LIRFunctionRestoreFrame,
    LIRFunctionReturn,
    LIRFunctionSaveFrame,
    LIRJumpIfZero,
    LIRLabel,
    LIRLoadMemoryAddress,
    LIRLogicalCompareRegisters,
    LIRModulusRegs,
    LIRMulRegs,
    LIRPopFromStackIntoRegisters,
    LIRPushInteger32Bits,
    LIRPushLocalFrameVariableAddress,
    LIRPushRegistersOntoStack,
    LIRPushStaticGlobalVariableAddress,
    LIRPushStaticStringAddress,
    LIRStoreIntoMemoryAddress,
    LIRSubRegs,
    LIRSystemCall,
    LIRSystemCallPrepareArguments,
    LIRSystemExit,
    LIRUnconditionalJumpToLabel,
)
from gofra.codegen.lir.registers import LIRVirtualRegister
from gofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from gofra.targets.target import Target

from .assembly import (
    function_acquire_arguments,
    function_call_prepare_arguments,
    function_prepare_retval,
    function_restore_frame,
    function_save_frame,
    initialize_static_data_section,
    ipc_syscall_macos,
    push_register_onto_stack,
    syscall_prepare_arguments,
)
from .registers import (
    AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
    AARCH64_STACK_ALIGNMENT,
    AARCH64_STACK_ALIGNMENT_BIN,
)

if TYPE_CHECKING:
    from gofra.hir.module import Module


target = Target.from_triplet("arm64-apple-darwin")


def generate_aarch64_lir_macos_backend(
    fd: IO[str],
    program: Module,
    target: Target,
) -> None:
    """AARCH64 MacOS code generation backend."""
    _ = target
    context = AARCH64CodegenContext(fd=fd, strings={})
    lir = translate_hir_to_lir(
        program,
        system_entry_point_name=LINKER_EXPECTED_ENTRY_POINT,
        virtual_register_allocator=context.vreg_allocator,
    )
    aarch64_macos_executable_functions(context, lir)
    initialize_static_data_section(context, lir)


def aarch64_macos_operator_instructions(
    context: AARCH64CodegenContext,
    operation: LIRBaseOp,
) -> None:
    context.write(f"// ; {operation} {operation.source_location}")

    match operation:
        case LIRSystemExit():
            # Call syscall to exit without accessing protected system memory.
            # `ret` into return-address will fail with segfault
            ipc_syscall_macos(
                context,
                arguments_count=1,
                store_retval_onto_stack=False,
                injected_args=[
                    AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
                    0,
                ],
            )
        case LIRFunctionAcquireArguments():
            function_acquire_arguments(context, operation.arguments)
        case LIRPushInteger32Bits():
            push_integer_onto_stack(context, operation.value)
        case LIRPopFromStackIntoRegisters():
            for vreg in operation.registries[::-1]:
                context.write(
                    f"ldr {vreg.name}, [SP]",
                    f"add SP, SP, #{AARCH64_STACK_ALIGNMENT}",
                )
        case LIRPushRegistersOntoStack():
            for vreg in operation.registries[::-1]:
                context.write(
                    f"str {vreg.name}, [SP]",
                    f"sub SP, SP, #-{AARCH64_STACK_ALIGNMENT}",
                )
        case LIRStoreIntoMemoryAddress():
            addr_reg = operation.address_register.name
            val_reg = operation.value_register.name

            context.write(f"str {val_reg}, [{addr_reg}]")
        case LIRLoadMemoryAddress():
            addr_reg = operation.address_register.name
            res_reg = operation.result_register.name
            context.write(f"ldr {res_reg}, [{addr_reg}]")
        case LIRDebuggerTraceTrap():
            context.write("brk #0")
        case (
            LIRAddRegs()
            | LIRLogicalCompareRegisters()
            | LIRModulusRegs()
            | LIRFloorDivRegs()
            | LIRSubRegs()
            | LIRMulRegs()
            | LIRBitwiseAndRegs()
            | LIRBitwiseOrRegs()
        ):
            res_reg = operation.result_register.name
            a_reg_or_imm = (
                operation.operand_a.name
                if isinstance(operation.operand_a, LIRVirtualRegister)
                else f"#{operation.operand_a.value}"
            )
            b_reg_or_imm = (
                operation.operand_b.name
                if isinstance(operation.operand_b, LIRVirtualRegister)
                else f"#{operation.operand_b.value}"
            )
            match operation:
                case LIRBitwiseAndRegs():
                    context.write(f"and {res_reg}, {a_reg_or_imm}, {b_reg_or_imm}")
                case LIRBitwiseOrRegs():
                    context.write(f"orr {res_reg}, {a_reg_or_imm}, {b_reg_or_imm}")
                case LIRMulRegs():
                    context.write(f"mul {res_reg}, {a_reg_or_imm}, {b_reg_or_imm}")
                case LIRAddRegs():
                    context.write(f"add {res_reg}, {a_reg_or_imm}, {b_reg_or_imm}")
                case LIRSubRegs():
                    context.write(f"sub {res_reg}, {a_reg_or_imm}, {b_reg_or_imm}")
                case LIRFloorDivRegs():
                    context.write(f"sdiv {res_reg}, {a_reg_or_imm}, {b_reg_or_imm}")
                case LIRModulusRegs():
                    temp_vreg = context.vreg_allocator.next_free_machine_register()
                    context.write(
                        f"udiv {temp_vreg}, {b_reg_or_imm}, {a_reg_or_imm}",
                        f"mul {temp_vreg}, {temp_vreg}, {a_reg_or_imm}",
                        f"sub {res_reg}, {b_reg_or_imm}, {temp_vreg}",
                    )
                case LIRLogicalCompareRegisters():
                    logic_op = {
                        "!=": "ne",
                        ">=": "ge",
                        "<=": "le",
                        "<": "lt",
                        ">": "gt",
                        "==": "eq",
                    }
                    context.write(f"cmp {a_reg_or_imm}, {b_reg_or_imm}")
                    context.write(f"cset {res_reg}, {logic_op[operation.comparison]}")
        case LIRUnconditionalJumpToLabel():
            context.write(f"b {operation.label}")
        case LIRFunctionCallPrepareArguments():
            function_call_prepare_arguments(context, operation.arguments)
        case LIRSystemCallPrepareArguments():
            syscall_prepare_arguments(context, operation.arguments_count - 1)
        case LIRLabel():
            context.fd.write(f"{operation.label}:")
        case LIRJumpIfZero():
            context.write(
                f"cmp {operation.register.name}, #0",
                f"beq {operation.label}",
            )
        case LIRFunctionCall():
            context.write(f"bl {operation.function}")
        case LIRPushLocalFrameVariableAddress():
            # name
            raise NotImplementedError
        case LIRFunctionCallAcquireRetval():
            push_register_onto_stack(context, "X0")
        case LIRSystemCall():
            context.write("svc #0")
            push_register_onto_stack(context, context.abi.return_value_register)
        case LIRPushStaticGlobalVariableAddress():
            push_static_address_onto_stack(context, operation.name)
        case LIRFunctionReturn():
            context.write("ret")
        case LIRFunctionPrepareRetval():
            function_prepare_retval(context)
        case LIRFunctionRestoreFrame():
            function_restore_frame(context)
        case LIRDropStackSlot():
            drop_stack_slots(context, slots_count=1)
        case LIRFunctionSaveFrame():
            function_save_frame(context, local_vars=operation.locals)
        case LIRPushStaticStringAddress():
            push_static_address_onto_stack(context, operation.segment)
        case _:
            msg = f"""
Codegen currently does not support LIR operation: {operation.__class__.__name__}!
LIR_INSTRUCTION: {operation}"""
            raise NotImplementedError(msg)


def aarch64_macos_executable_functions(
    context: AARCH64CodegenContext,
    lir: LIRProgram,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    for function in lir.functions.values():
        if function.is_global_linker_symbol:
            context.fd.write(f".global {function.name}\n")

        context.fd.write(f".align {AARCH64_STACK_ALIGNMENT_BIN}\n")
        context.fd.write(f"{function.name}:\n")
        assert function.operations, "Empty LIR function body"
        for operation in function.operations:
            aarch64_macos_operator_instructions(context, operation)
