# Perform all possible tests at user side, CI uses a bit different approach

# Migrate to `set -xe` after fix with colors, TODO!
set -e
gofra-testkit -d examples --build-only -p "*_*.gof" -e 03_pong.gof -s 
gofra-testkit -d tests -s
gofra ./examples/03_pong.gof -lraylib