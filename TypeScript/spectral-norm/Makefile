LANG        = TypeScript
TEST        = spectral-norm
SOURCE      = spectralnorm.ts
OUTPUT      = spectral-norm.js
ARG         = 5500
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
