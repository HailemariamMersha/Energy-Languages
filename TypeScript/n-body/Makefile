LANG        = TypeScript
TEST        = n-body
SOURCE      = nbody.typescript-3.ts
OUTPUT      = n-body.js
ARG         = 50000000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
