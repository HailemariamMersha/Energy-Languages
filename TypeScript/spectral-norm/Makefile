LANG        = TypeScript
TEST        = spectral-norm
SOURCE      = spectralnorm.ts
OUTPUT      = spectral-norm.js
ARG         = 5500
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= tsc

COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
