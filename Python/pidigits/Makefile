LANG        = Python
TEST        = pidigits
SOURCE      = pidigits.python3-2.python3
OUTPUT      = pidigits.py
ARG         = 10000
PYTHON      ?= python3
RUN_CMD     = $(PYTHON) -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 28
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
