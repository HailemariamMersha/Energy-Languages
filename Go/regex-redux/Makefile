LANG    = Go
TEST    = regex-redux
SOURCE  = regexredux.go-2.go
OUTPUT  = regex-redux.go_run
ARG     = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/regex-redux.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
