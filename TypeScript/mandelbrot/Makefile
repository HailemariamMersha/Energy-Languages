LANG        = TypeScript
TEST        = mandelbrot
SOURCE      = mandelbrot.ts
OUTPUT      = mandelbrot.js
ARG         = 16000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= tsc

COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
