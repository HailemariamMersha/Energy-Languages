LANG    = Go
TEST    = pidigits
SOURCE  = pidigits.go-3.go
OUTPUT  = pidigits.go_run
ARG     = 10000
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 27
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
