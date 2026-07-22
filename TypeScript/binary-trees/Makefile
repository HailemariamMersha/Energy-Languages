LANG        = TypeScript
TEST        = binary-trees
SOURCE      = binarytrees.typescript-2.ts
OUTPUT      = binary-trees.js
ARG         = 21
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
