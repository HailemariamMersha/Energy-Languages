LANG        = TypeScript
TEST        = n-body
SOURCE      = nbody.typescript-3.ts
OUTPUT      = n-body.js
ARG         = 50000000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= tsc

COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
