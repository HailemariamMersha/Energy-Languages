LANG    = Go
TEST    = binary-trees
SOURCE  = binarytrees.go-2.go
OUTPUT  = binary-trees.go_run
ARG     = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
