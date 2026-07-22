LANG        = TypeScript
TEST        = fannkuch-redux
SOURCE      = fannkuchredux.ts
OUTPUT      = fannkuch-redux.js
ARG         = 12
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
