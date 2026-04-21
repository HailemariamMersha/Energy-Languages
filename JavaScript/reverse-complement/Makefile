LANG        = JavaScript
TEST        = reverse-complement
SOURCE      = revcomp.node-7.node
OUTPUT      = reverse-complement.js
ARG         = 21
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/reverse-complement.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
