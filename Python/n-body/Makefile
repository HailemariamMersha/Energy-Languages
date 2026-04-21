LANG        = Python
TEST        = n-body
SOURCE      = nbody.python3
OUTPUT      = nbody.py
ARG         = 50000000
RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
