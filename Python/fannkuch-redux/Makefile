LANG        = Python
TEST        = fannkuch-redux
SOURCE      = fannkuchredux.python3-4.python3
OUTPUT      = fannkuchredux.py
ARG         = 12
PYTHON      ?= python3
RUN_CMD     = $(PYTHON) -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
