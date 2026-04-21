LANG    = Go
TEST    = k-nucleotide
SOURCE  = knucleotide.go-6.go
OUTPUT  = k-nucleotide.go_run
ARG     = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/k-nucleotide.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
