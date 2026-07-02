# Internal testkit (test runner)

Gofra comes with own test suite (testkit).
It is preinstalled with Gofra as `gofra-testkit`.

It is usable for core developers and possibly to ensure that all compiler stuff is working on the host machine while finding problems.

By default, running `gofra-testkit` in the repository root will find required testcases, but you can define own test cases within current directory (possible usage of `--pattern`)

## Test case specification

By default each test being compiled separately on its own, therefore you define constant macro to specify what scenario is treated an error and which is not.


### TESTKIT_EXPECT_COMPILE_ERROR

Expects compiler to throw an error while compiling at any stage with message containing macro

By default is not defined - no errors expected and any error will fail test case

```gofra
#define TESTKIT_EXPECT_COMPILE_ERROR "abc"
```

### TESTKIT_EXPECTED_EXIT_CODE

Expect test artifact to be finished with specified exit code

By default equals zero, default exit code for all the programs

```gofra
#define TESTKIT_EXPECTED_EXIT_CODE 1
```


### TESTKIT_EXPECTED_STDOUT

Expect test artifact will emit this to own stdout

By default is not defined means any stdout is allowed

```gofra
#define TESTKIT_EXPECTED_STDOUT "Hello, World!"
```