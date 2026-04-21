LANG        = JavaScript
TEST        = k-nucleotide
SOURCE      = knucleotide.node-2.node
OUTPUT      = k-nucleotide.js
ARG         = 21
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/k-nucleotide.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
