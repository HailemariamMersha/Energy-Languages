LANG        = Ruby
TEST        = mandelbrot
SOURCE      = mandelbrot.yarv-5.yarv
OUTPUT      = mandelbrot.rb
ARG         = 16000
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
