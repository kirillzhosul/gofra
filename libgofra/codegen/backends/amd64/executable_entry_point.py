from libgofra.codegen.backends.amd64.registers import (
    AMD64_LINUX_EPILOGUE_EXIT_CODE,
    AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER,
)
from libgofra.hir.function import Function
from libgofra.targets.target import Target
from libgofra.types.primitive.integers import I64Type
from libgofra.types.primitive.void import VoidType

from ._context import AMD64CodegenContext
from .assembly import (
    function_begin_with_prologue,
    function_call,
    function_end_with_epilogue,
    ipc_syscall_linux,
    push_integer_onto_stack,
)


def amd64_program_entry_point(
    context: AMD64CodegenContext,
    system_entry_point_name: str,
    entry_point: Function,
    target: Target,
) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # This is an executable entry point
    function_begin_with_prologue(
        context,
        function_name=system_entry_point_name,
        as_global_linker_symbol=True,
        preserve_frame=False,  # Unable to end with epilogue, but not required as this done via kernel OS
        arguments_count=0,
        local_variables={},
    )

    # Prepare and execute main function
    assert isinstance(entry_point.return_type, VoidType | I64Type)
    function_call(
        context,
        name=entry_point.name,
        type_contract_in=[],
        type_contract_out=entry_point.return_type,
    )

    match target.operating_system:
        case "Linux":
            _linux_sys_exit_epilogue(context, entry_point)
        case "Windows":
            _windows_sys_exit_epilogue(context, entry_point)
        case _:
            raise NotImplementedError

    function_end_with_epilogue(
        context=context,
        has_preserved_frame=False,
        return_type=VoidType(),
        execution_trap_instead_return=True,
    )


def _linux_sys_exit_epilogue(
    context: AMD64CodegenContext,
    entry_point: Function,
) -> None:
    # Call syscall to exit without accessing protected system memory.
    # `ret` into return-address will fail with segfault
    if not entry_point.has_return_value():
        # TODO!(@kirillzhosul): review exit code on Windows  # noqa: TD002, TD004
        # Call syscall to exit without accessing protected system memory.
        # `ret` into return-address will fail with segfault
        ipc_syscall_linux(
            context,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=[
                AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER,
                AMD64_LINUX_EPILOGUE_EXIT_CODE,
            ],
        )
    else:
        push_integer_onto_stack(context, AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER)
        ipc_syscall_linux(
            context,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=None,
        )


def _windows_sys_exit_epilogue(
    context: AMD64CodegenContext,
    entry_point: Function,
) -> None:
    # Call syscall to exit without accessing protected system memory.
    # `ret` into return-address will fail with segfault
    if not entry_point.has_return_value():
        push_integer_onto_stack(context, 0)
    # TODO(@kirillzhosul): review exit code on Windows
    _win_resolve_import("kernel32.dll", "ExitProcess")
    function_call(
        context,
        name="ExitProcess",
        type_contract_in=[I64Type()],
        type_contract_out=VoidType(),
    )


def _win_resolve_import(dll: str, func: str) -> None: ...
