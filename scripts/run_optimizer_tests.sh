# Perform baseline testcases (testkit) with optimizer passes at aggressive setting

# Migrate to `set -xe` after fix with colors, TODO!
set -e
gofra-testkit -d examples --build-only -p "*_*.gof" -e 03_pong.gof -s --aggressive-optimizations
gofra-testkit -d tests -s --aggressive-optimizations
gofra ./examples/03_pong.gof -lraylib -O1