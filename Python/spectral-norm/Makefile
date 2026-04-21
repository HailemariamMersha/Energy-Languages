LANG        = Python
TEST        = spectral-norm
SOURCE      = spectralnorm.python3-5.python3
OUTPUT      = spectralnorm.py
ARG         = 5500
RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
