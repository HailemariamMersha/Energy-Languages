LANG        = JavaScript
TEST        = fasta
SOURCE      = fasta.node-4.node
OUTPUT      = fasta.js
ARG         = 25000000
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
