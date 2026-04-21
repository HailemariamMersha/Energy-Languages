LANG        = Python
TEST        = mandelbrot
SOURCE      = mandelbrot.python3-7.python3
OUTPUT      = mandelbrot.py
ARG         = 16000
RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
