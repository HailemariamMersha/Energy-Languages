LANG        = Python
TEST        = fasta
SOURCE      = fasta.python3-3.python3
OUTPUT      = fasta.py
ARG         = 25000000
PYTHON      ?= python3
RUN_CMD     = $(PYTHON) -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
