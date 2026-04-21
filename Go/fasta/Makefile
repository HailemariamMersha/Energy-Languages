LANG    = Go
TEST    = fasta
SOURCE  = fasta.go-3.go
OUTPUT  = fasta.go_run
ARG     = 25000000
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
