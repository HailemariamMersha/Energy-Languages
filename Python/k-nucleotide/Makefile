LANG        = Python
TEST        = k-nucleotide
SOURCE      = knucleotide.python3-3.python3
OUTPUT      = knucleotide.py
ARG         = 21
RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/k-nucleotide.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
