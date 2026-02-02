from libgofra.codegen.abi import AARCH64ABI
from libgofra.codegen.backends.aarch64.svc_syscall import ipc_aarch64_syscall
from libgofra.codegen.backends.aarch64.writer import WriterProtocol
from libgofra.hir.function import Function
from libgofra.targets.target import Target
from libgofra.types.primitive.integers import I64Type
from libgofra.types.primitive.void import VoidType

from .abi_call_convention import function_abi_call_by_symbol
from .primitive_instructions import push_integer_onto_stack
from .subroutines import function_begin_with_prologue, function_end_with_epilogue

# TODO: Refactor and move away from here (gofra source / abstraction)?
AARCH64_MACOS_EPILOGUE_EXIT_CODE = 0
AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER = 1


def aarch64_program_entry_point(
    writer: WriterProtocol,
    abi: AARCH64ABI,
    system_entry_point_name: str,
    entry_point: Function,
    target: Target,
) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # TODO: add flag like `--bare-entry` to allow specify that Gofra `main` is real main
    # also requires reworking entry point flags / specification

    # This is an executable entry point
    function_begin_with_prologue(
        writer,
        abi,
        name=system_entry_point_name,
        global_name=system_entry_point_name,
        preserve_frame=False,  # Unable to end with epilogue, but not required as this done via kernel OS
        local_variables={},
        string_pool=None,
        parameters=[],
    )

    # Prepare and execute main function
    assert isinstance(entry_point.return_type, VoidType | I64Type)
    function_abi_call_by_symbol(
        writer,
        abi,
        name=entry_point.name,
        parameters=[],
        return_type=entry_point.return_type,
        call_convention="apple_aapcs64",  # TODO: allow to specify / override call-conv?
    )

    assert target.operating_system == "Darwin"
    _darwin_sys_exit_epilogue(writer, abi, entry_point)

    function_end_with_epilogue(
        writer,
        abi=abi,
        has_preserved_frame=False,
        return_type=VoidType(),
        is_early_return=False,
    )


def _darwin_sys_exit_epilogue(
    writer: WriterProtocol,
    abi: AARCH64ABI,
    entry_point: Function,
) -> None:
    # Call syscall to exit without accessing protected system memory.
    # `ret` into return-address will fail with segfault
    if entry_point.has_return_value():
        push_integer_onto_stack(writer, AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER)
        ipc_aarch64_syscall(
            writer,
            abi,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=None,
        )
    else:
        ipc_aarch64_syscall(
            writer,
            abi,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=[
                AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
                AARCH64_MACOS_EPILOGUE_EXIT_CODE,
            ],
        )
