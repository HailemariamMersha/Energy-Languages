LANG        = Python
TEST        = pidigits
SOURCE      = pidigits.python3-2.python3
OUTPUT      = pidigits.py
ARG         = 10000
RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 27
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
