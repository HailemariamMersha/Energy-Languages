LANG        = TypeScript
TEST        = pidigits
SOURCE      = pidigits.ts
OUTPUT      = pidigits.js
ARG         = 10000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 28
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
