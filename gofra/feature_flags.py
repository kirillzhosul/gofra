"""Some hardcoded feature flags that is not yet in the language but something like an proposal.

They may break existing code or be buggy, so they are separate into flags
You can enable them to try or to develop.
"""

# Translate to LIR from HIR at codegen level instead of HIR to machine code translation
# Disabled due to current in-progress implementation and bugs
FEATURE_USE_LIR_CODEGEN_IR = False

FEATURE_ALLOW_FPU = False
