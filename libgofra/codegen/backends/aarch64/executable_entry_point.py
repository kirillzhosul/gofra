from libgofra.codegen.backends.aarch64.svc_syscall import (
    AARCH64_MACOS_EPILOGUE_EXIT_CODE,
    AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
    ipc_aarch64_syscall,
)
from libgofra.hir.function import Function
from libgofra.targets.target import Target
from libgofra.types.primitive.integers import I64Type
from libgofra.types.primitive.void import VoidType

from ._context import AARCH64CodegenContext
from .abi_call_convention import function_abi_call_by_symbol
from .primitive_instructions import push_integer_onto_stack
from .subroutines import function_begin_with_prologue, function_end_with_epilogue


def aarch64_program_entry_point(
    context: AARCH64CodegenContext,
    system_entry_point_name: str,
    entry_point: Function,
    target: Target,
) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # This is an executable entry point
    function_begin_with_prologue(
        context,
        name=system_entry_point_name,
        global_name=system_entry_point_name,
        preserve_frame=False,  # Unable to end with epilogue, but not required as this done via kernel OS
        local_variables={},
        parameters=[],
    )

    # Prepare and execute main function
    assert isinstance(entry_point.return_type, VoidType | I64Type)
    function_abi_call_by_symbol(
        context,
        name=entry_point.name,
        parameters=[],
        return_type=entry_point.return_type,
        call_convention="apple_aapcs64",
    )

    assert target.operating_system == "Darwin"
    _darwin_sys_exit_epilogue(context, entry_point)

    function_end_with_epilogue(
        context=context,
        has_preserved_frame=False,
        return_type=VoidType(),
        is_early_return=False,
    )


def _darwin_sys_exit_epilogue(
    context: AARCH64CodegenContext,
    entry_point: Function,
) -> None:
    # Call syscall to exit without accessing protected system memory.
    # `ret` into return-address will fail with segfault
    if isinstance(entry_point.return_type, VoidType):
        ipc_aarch64_syscall(
            context,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=[
                AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
                AARCH64_MACOS_EPILOGUE_EXIT_CODE,
            ],
        )
    else:
        push_integer_onto_stack(context, AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER)
        ipc_aarch64_syscall(
            context,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=None,
        )
