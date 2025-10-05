import subprocess

SYSCALL_MACRO_PREFIX = "SYS_"
SYSTEM_INCLUDES = [
    "-isystem",
    "/usr/include",
    "-isystem",
    "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include",
]


def extract_raw_kernel_syscall_macro_definitions(
    *,
    include_max_syscall: bool = False,
) -> dict[str, int]:
    """Extract all syscall numbers defined inside macros (e.g C/C++ #define) that is included in c stdlib from kernel.

    They are used for making syscalls from C/C++ but we extracting them for fresh real-time mapping of all syscalls

    Implementation:
        Calls to C compiler to preprocess an file with include of syscall header
        Then extracts all definitions that starts with SYS_* (e.g all syscall numbers) and returns to the caller
    """
    cmd = ["cc", "-E", "-dM", "-", *SYSTEM_INCLUDES]
    source = b"#include <sys/syscall.h>"

    process = subprocess.run(
        cmd,
        input=source,
        stdout=subprocess.PIPE,
        check=True,
    )

    stdout = process.stdout.decode()

    syscalls: dict[str, int] = {}
    it = (
        line
        for line in stdout.split("\n")
        if line.startswith(f"#define {SYSCALL_MACRO_PREFIX}")
    )
    for line in it:
        _, name, value, *_ = line.split()
        if "__" in name:
            continue
        name = name.removeprefix(SYSCALL_MACRO_PREFIX)
        syscalls[name] = int(value)

    if not include_max_syscall:
        syscalls.pop("MAXSYSCALL")
    return dict(sorted(syscalls.items(), key=lambda x: x[1]))


if __name__ == "__main__":
    raw_syscalls = extract_raw_kernel_syscall_macro_definitions()
    for syscall_name, syscall_number in raw_syscalls.items():
        print(syscall_name, "=", syscall_number)
