"""Some hardcoded feature flags that is not yet in the language but something like an proposal.

They may break existing code or be buggy, so they are separate into flags
You can enable them to try or to develop.
"""

# Allow to use float-values
# FULLY UNSTABLE and has too few features
# Merge plan: Full FP support like integers
FEATURE_ALLOW_FPU = False

# Will be `import` allowed?
# Merge plan: Finish implementation, close caveats, remove preprocessor direct include? (with exchange)
FEATURE_ALLOW_MODULES = False
