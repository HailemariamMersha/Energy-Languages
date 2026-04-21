LANG        = TypeScript
TEST        = fannkuch-redux
SOURCE      = fannkuchredux.ts
OUTPUT      = fannkuch-redux.js
ARG         = 12
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= tsc

COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
