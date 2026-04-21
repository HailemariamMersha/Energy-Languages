LANG    = Go
TEST    = reverse-complement
SOURCE  = revcomp.go-6.go
OUTPUT  = reverse-complement.go_run
ARG     = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/reverse-complement.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
