"""LIR (low-level-intermediate-representation). For supported codegen."""

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Literal, assert_never

from gofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from gofra.context import ProgramContext
from gofra.parser.functions.function import Function
from gofra.parser.intrinsics import Intrinsic
from gofra.parser.operators import OperatorType
from gofra.types.primitive.void import VoidType

from .function import (
    LIRExternFunction,
    LIRFunction,
    LIRInternalFunction,
    LIRParameter,
)
from .ops import (
    LIRAddRegs,
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
from .registers import LIRImmediate, LIRVirtualRegister, LIRVirtualRegisterAllocator
from .static import (
    LIRStaticSegment,
    LIRStaticSegmentCString,
    LIRStaticSegmentGlobalVariable,
)


@dataclass
class LIRProgram:
    static_segment: MutableMapping[str, LIRStaticSegment]
    functions: MutableMapping[str, LIRInternalFunction]
    externs: MutableMapping[str, LIRExternFunction]

    def get_function(self, name: str) -> LIRFunction:
        local = self.functions.get(name)
        if local:
            return local
        return self.externs[name]


def hir_global_variables_to_lir_static_variables(
    hir: ProgramContext,
) -> MutableMapping[str, LIRStaticSegment]:
    return {
        var.name: LIRStaticSegmentGlobalVariable(
            name=var.name,
            type=var.type,
        )
        for var in hir.global_variables.values()
    }


def translate_hir_to_lir(
    hir: ProgramContext,
    system_entry_point_name: str | None,
    virtual_register_allocator: LIRVirtualRegisterAllocator,
) -> LIRProgram:
    static_global_variables = hir_global_variables_to_lir_static_variables(hir)
    lir = LIRProgram(
        static_segment=static_global_variables,
        functions={},
        externs={},
    )

    for hir_func in (*hir.functions.values(), hir.entry_point):
        name = hir_func.name
        if hir_func.external_definition_link_to:
            lir.externs[name] = hir_external_function_to_lir_extern_function(hir_func)
            continue
        lir.functions[name] = translate_hir_function_to_lir_function(
            lir,
            hir_func,
            virtual_register_allocator,
        )

    if system_entry_point_name:
        assert system_entry_point_name not in lir.functions
        lir.functions[system_entry_point_name] = lir_generate_system_entry_point(
            system_ep_name=system_entry_point_name,
            internal_ep_name=hir.entry_point.name,
        )
    return lir


def lir_generate_system_entry_point(
    system_ep_name: str,
    internal_ep_name: str,
) -> LIRInternalFunction:
    sep = LIRInternalFunction(
        name=system_ep_name,
        return_type=VoidType(),
        is_global_linker_symbol=True,
        locals={},
        parameters=[],
    )

    sep.add_op(LIRFunctionCall(internal_ep_name))
    sep.add_op(LIRSystemExit())
    sep.add_op(LIRDebuggerTraceTrap())
    return sep


def hir_external_function_to_lir_extern_function(
    hir_function: Function,
) -> LIRExternFunction:
    assert hir_function.external_definition_link_to
    params = [LIRParameter(t) for t in hir_function.type_contract_in]
    return LIRExternFunction(
        name=hir_function.external_definition_link_to,
        real_name=hir_function.name,
        return_type=hir_function.type_contract_out,
        parameters=params,
    )


def translate_hir_function_to_lir_function(
    lir: LIRProgram,
    hir_function: Function,
    virtual_register_allocator: LIRVirtualRegisterAllocator,
) -> LIRInternalFunction:
    assert hir_function.external_definition_link_to is None
    parameters = [LIRParameter(t) for t in hir_function.type_contract_in]
    f_local_vars = {v.name: v.type for v in hir_function.variables.values()}

    lir_function = LIRInternalFunction(
        name=hir_function.name,
        is_global_linker_symbol=hir_function.is_global_linker_symbol,
        return_type=hir_function.type_contract_out,
        parameters=parameters,
        locals=f_local_vars,
    )

    is_leaf_function = True
    retval_type = hir_function.type_contract_out
    has_retval = retval_type.size_in_bytes != 0

    lir_function.add_op(LIRFunctionSaveFrame(locals=f_local_vars))

    if parameters:
        lir_function.add_op(LIRFunctionAcquireArguments([p.type for p in parameters]))

    def vreg_alloc() -> LIRVirtualRegister:
        return LIRVirtualRegister(allocator=virtual_register_allocator)

    for idx, operator in enumerate(hir_function.source):
        virtual_register_allocator.reset_virtual_space()
        lir_function.update_location(operator.token.location)

        match operator.type:
            case OperatorType.FUNCTION_RETURN:
                lir_function.add_op(
                    LIRFunctionRestoreFrame(locals=list(f_local_vars.values())),
                )
                if has_retval:
                    lir_function.add_op(LIRFunctionPrepareRetval(retval_type))
                lir_function.add_op(LIRFunctionReturn())
            case OperatorType.FUNCTION_CALL:
                assert isinstance(operator.operand, str)

                # Mark function as leaf one ASAP.
                is_leaf_function = False

                name = operator.operand
                func = lir.get_function(name)

                lir_function.add_op(
                    LIRFunctionCallPrepareArguments(
                        arguments=[p.type for p in func.parameters],
                    ),
                )
                lir_function.add_op(LIRFunctionCall(func.name))
                if func.return_type.size_in_bytes != 0:
                    lir_function.add_op(
                        LIRFunctionCallAcquireRetval(return_type=func.return_type),
                    )

            case OperatorType.TYPECAST:
                # Skip that as it is typechecker only.
                pass
            case OperatorType.VARIABLE_DEFINE:
                msg = "Parser must resolve variable definition before LIR-cogeneration"
                raise ValueError(msg)
            case OperatorType.PUSH_INTEGER:
                assert isinstance(operator.operand, int)
                lir_function.add_op(LIRPushInteger32Bits(operator.operand))
            case OperatorType.PUSH_MEMORY_POINTER:
                assert isinstance(operator.operand, tuple)
                name, _ = operator.operand
                if name in lir_function.locals:
                    lir_function.add_op(LIRPushLocalFrameVariableAddress(name=name))
                else:
                    lir_function.add_op(LIRPushStaticGlobalVariableAddress(name=name))
            case OperatorType.DO | OperatorType.IF:
                assert isinstance(operator.jumps_to_operator_idx, int)
                vreg = vreg_alloc()

                # TODO(@kirillzhosul): introduce relative jumps or label-stack
                # label stack in case of jump-instr we push something on that stack
                # so next time when we close that block we define an label on top of stack
                label = CODEGEN_GOFRA_CONTEXT_LABEL % (
                    lir_function.name,
                    operator.jumps_to_operator_idx,
                )
                lir_function.add_ops(
                    LIRPopFromStackIntoRegisters((vreg,)),
                    LIRJumpIfZero(register=vreg, label=label),
                )
            case OperatorType.INTRINSIC:
                assert isinstance(operator.operand, Intrinsic)
                assert operator.type == OperatorType.INTRINSIC
                match operator.operand:
                    case Intrinsic.DROP:
                        lir_function.add_op(LIRDropStackSlot())
                    case Intrinsic.COPY:
                        vreg = vreg_alloc()
                        lir_function.add_op(LIRPopFromStackIntoRegisters([vreg]))
                        lir_function.add_op(LIRPushRegistersOntoStack([vreg, vreg]))
                    case Intrinsic.SWAP:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters([vreg_a, vreg_b]),
                            LIRPushRegistersOntoStack([vreg_b, vreg_a]),
                        )
                    case (
                        Intrinsic.SYSCALL0
                        | Intrinsic.SYSCALL1
                        | Intrinsic.SYSCALL2
                        | Intrinsic.SYSCALL3
                        | Intrinsic.SYSCALL4
                        | Intrinsic.SYSCALL5
                        | Intrinsic.SYSCALL6
                    ):
                        assert operator.syscall_optimization_injected_args is None
                        assert operator.syscall_optimization_omit_result is False
                        syscall_args = operator.get_syscall_arguments_count()
                        lir_function.add_ops(
                            LIRSystemCallPrepareArguments(syscall_args),
                            LIRSystemCall(),
                        )
                    case Intrinsic.BREAKPOINT:
                        lir_function.add_op(LIRDebuggerTraceTrap())
                    case Intrinsic.MEMORY_LOAD:
                        vreg = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg,)),
                            LIRLoadMemoryAddress(
                                address_register=vreg,
                                result_register=vreg,
                            ),
                            LIRPushRegistersOntoStack((vreg,)),
                        )
                    case Intrinsic.MEMORY_STORE:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()

                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRStoreIntoMemoryAddress(
                                address_register=vreg_a,
                                value_register=vreg_b,
                            ),
                        )
                    case Intrinsic.INCREMENT:
                        vreg = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg,)),
                            LIRAddRegs(
                                result_register=vreg,
                                operand_a=vreg,
                                operand_b=LIRImmediate(value=1),
                            ),
                            LIRPushRegistersOntoStack((vreg,)),
                        )
                    case Intrinsic.DECREMENT:
                        vreg = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg,)),
                            LIRSubRegs(
                                result_register=vreg,
                                operand_a=vreg,
                                operand_b=LIRImmediate(value=1),
                            ),
                            LIRPushRegistersOntoStack((vreg,)),
                        )
                    case Intrinsic.PLUS:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()

                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRAddRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.MINUS:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRSubRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.MULTIPLY:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRMulRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.DIVIDE:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRFloorDivRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.MODULUS:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRModulusRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.BITWISE_AND:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRBitwiseAndRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.BITWISE_OR:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRBitwiseOrRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.LOGICAL_OR:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRBitwiseOrRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case Intrinsic.BITSHIFT_RIGHT:
                        raise NotImplementedError
                    case Intrinsic.BITSHIFT_LEFT:
                        raise NotImplementedError
                    case Intrinsic.LOGICAL_AND:
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRBitwiseAndRegs(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case (
                        Intrinsic.NOT_EQUAL
                        | Intrinsic.GREATER_EQUAL_THAN
                        | Intrinsic.LESS_EQUAL_THAN
                        | Intrinsic.LESS_THAN
                        | Intrinsic.GREATER_THAN
                        | Intrinsic.EQUAL
                    ):
                        vreg_a = vreg_alloc()
                        vreg_b = vreg_alloc()
                        comp_map: dict[
                            Intrinsic,
                            Literal["!=", ">=", "<=", "<", ">", "=="],
                        ] = {
                            Intrinsic.NOT_EQUAL: "!=",
                            Intrinsic.GREATER_EQUAL_THAN: ">=",
                            Intrinsic.LESS_EQUAL_THAN: "<=",
                            Intrinsic.LESS_THAN: "<",
                            Intrinsic.GREATER_THAN: ">",
                            Intrinsic.EQUAL: "==",
                        }
                        lir_function.add_ops(
                            LIRPopFromStackIntoRegisters((vreg_a, vreg_b)),
                            LIRLogicalCompareRegisters(
                                result_register=vreg_a,
                                operand_a=vreg_a,
                                operand_b=vreg_b,
                                comparison=comp_map[operator.operand],
                            ),
                            LIRPushRegistersOntoStack((vreg_a,)),
                        )
                    case _:
                        assert_never(operator.operand)

            case OperatorType.PUSH_STRING:
                assert isinstance(operator.operand, str)
                string_raw = str(operator.token.text[1:-1])

                next_string_segment_id = len(
                    [
                        s
                        for s in lir.static_segment
                        if isinstance(s, LIRStaticSegmentCString)
                    ],
                )

                # Add new static string in LIR section
                segment = LIRStaticSegmentCString(
                    text=string_raw,
                    name=f"str{next_string_segment_id}",
                )
                lir.static_segment[segment.name] = segment

                lir_function.add_op(
                    LIRPushStaticStringAddress(segment=segment.name),
                )
                lir_function.add_op(LIRPushInteger32Bits(len(string_raw)))
            case OperatorType.END | OperatorType.WHILE:
                label = CODEGEN_GOFRA_CONTEXT_LABEL % (lir_function.name, idx)
                if isinstance(operator.jumps_to_operator_idx, int):
                    label_to = CODEGEN_GOFRA_CONTEXT_LABEL % (
                        lir_function.name,
                        operator.jumps_to_operator_idx,
                    )
                    lir_function.add_op(LIRUnconditionalJumpToLabel(label_to))
                lir_function.add_op(LIRLabel(label))
            case _:
                assert_never(operator.type)

    has_to_backpatch_for_leaf_function = is_leaf_function and not f_local_vars
    has_to_backpatch_for_leaf_function = False

    if has_to_backpatch_for_leaf_function:
        save_frame_op = lir_function.operations.pop(0)
        assert isinstance(save_frame_op, LIRFunctionSaveFrame), save_frame_op

    if not has_to_backpatch_for_leaf_function:
        lir_function.add_op(LIRFunctionRestoreFrame(locals=list(f_local_vars.values())))

    if has_retval:
        lir_function.add_ops(
            LIRFunctionPrepareRetval(retval_type),
            LIRFunctionReturn(),
        )

    return lir_function
