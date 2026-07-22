LANG        = Python
TEST        = regex-redux
SOURCE      = regexredux.python3
OUTPUT      = regexredux.py
ARG         = 0
PYTHON      ?= python3
RUN_CMD     = $(PYTHON) -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/regex-redux.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
