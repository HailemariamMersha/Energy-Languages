LANG        = TypeScript
TEST        = binary-trees
SOURCE      = binarytrees.typescript-2.ts
OUTPUT      = binary-trees.js
ARG         = 21
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= tsc

COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
