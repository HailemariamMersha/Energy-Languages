LANG        = Python
TEST        = spectral-norm
SOURCE      = spectralnorm.python3-5.python3
OUTPUT      = spectralnorm.py
ARG         = 5500
PYTHON      ?= python3
RUN_CMD     = $(PYTHON) -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
