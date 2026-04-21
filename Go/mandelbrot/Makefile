LANG    = Go
TEST    = mandelbrot
SOURCE  = mandelbrot.go-3.go
OUTPUT  = mandelbrot.go_run
ARG     = 16000
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
