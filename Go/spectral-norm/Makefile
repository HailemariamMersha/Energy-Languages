LANG    = Go
TEST    = spectral-norm
SOURCE  = spectralnorm.go-4.go
OUTPUT  = spectral-norm.go_run
ARG     = 5500
RUN_CMD = ./$(OUTPUT) $(ARG)

COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
