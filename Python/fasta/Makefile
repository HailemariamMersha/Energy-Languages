LANG        = Python
TEST        = fasta
SOURCE      = fasta.python3-3.python3
OUTPUT      = fasta.py
ARG         = 25000000
RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
