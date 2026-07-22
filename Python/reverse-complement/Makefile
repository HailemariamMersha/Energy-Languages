LANG        = Python
TEST        = reverse-complement
SOURCE      = revcomp.python3-6.python3
OUTPUT      = revcomp.py
ARG         = 0
PYTHON      ?= python3
RUN_CMD     = $(PYTHON) -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/reverse-complement.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
