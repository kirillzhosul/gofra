gofra-testkit -d examples --build-only -p "*_*.gof" -e 03_pong.gof -s
gofra-testkit -d tests -s
gofra ./examples/03_pong.gof -lraylib