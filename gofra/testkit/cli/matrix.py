from gofra.cli.output import CLIColor
from gofra.testkit.test import Test, TestStatus

COLORS: dict[TestStatus, str] = {
    TestStatus.SUCCESS: CLIColor.GREEN,
    TestStatus.TOOLCHAIN_ERROR: CLIColor.RED,
    TestStatus.EXECUTION_STATUS_ERROR: CLIColor.RED,
    TestStatus.SKIPPED: CLIColor.RESET,
}

ICONS: dict[TestStatus, str] = {
    TestStatus.SUCCESS: "+",
    TestStatus.TOOLCHAIN_ERROR: "-",
    TestStatus.EXECUTION_TIMEOUT_ERROR: "@",
    TestStatus.EXECUTION_STATUS_ERROR: "@",
    TestStatus.SKIPPED: ".",
}


def display_test_matrix(matrix: list[Test]) -> None:
    for test in matrix:
        color = COLORS[test.status]
        icon = ICONS[test.status]
        print(f"{color}{icon}", test.path)
