LANG        = JavaScript
TEST        = mandelbrot
SOURCE      = mandelbrot.node
OUTPUT      = mandelbrot.js
ARG         = 16000
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
