LANG        = JavaScript
TEST        = spectral-norm
SOURCE      = spectralnorm.node-2.node
OUTPUT      = spectral-norm.js
ARG         = 5500
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
