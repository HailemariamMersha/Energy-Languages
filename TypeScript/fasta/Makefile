LANG        = TypeScript
TEST        = fasta
SOURCE      = fasta.ts
OUTPUT      = fasta.js
ARG         = 25000000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= tsc

COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
