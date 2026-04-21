LANG    = Go
TEST    = n-body
SOURCE  = nbody.go
OUTPUT  = n-body.go_run
ARG     = 50000000
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
