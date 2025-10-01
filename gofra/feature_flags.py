"""Some hardcoded feature flags that is not yet in the language but something like an proposal.

They may break existing code or be buggy, so they are separate into flags
You can enable them to try or to develop.
"""

# Dereference variable by default
#
# Old:
# var age int
# age 0 !< // store
# age ?> // load
#
# New:
# var age int
# &age 0 !< // store
# age // load
#
# Disabled due to current prototyping and improvement process
FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT = False
