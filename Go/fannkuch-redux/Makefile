LANG    = Go
TEST    = fannkuch-redux
SOURCE  = fannkuchredux.go
OUTPUT  = fannkuch-redux.go_run
ARG     = 12
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
