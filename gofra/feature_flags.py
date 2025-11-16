"""Some hardcoded feature flags that is not yet in the language but something like an proposal.

They may break existing code or be buggy, so they are separate into flags
You can enable them to try or to develop.
"""

# Translate to LIR from HIR at codegen level instead of HIR to machine code translation
# Disabled due to current in-progress implementation and bugs
# Merge plan: Rewrite LIR and use LIR in all code generators
FEATURE_USE_LIR_CODEGEN_IR = False

# Allow to use float-values
# FULLY UNSTABLE and has too few features
# Merge plan: Full FP support like integers
FEATURE_ALLOW_FPU = False

# Will always generate OOB check with panic (abort)
# on OOB within array access
# Merge plan: add under flag, optimize usages of OOB check (not always)
FEATURE_RUNTIME_ARRAY_OOB_CHECKS = False
