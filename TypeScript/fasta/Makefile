LANG        = TypeScript
TEST        = fasta
SOURCE      = fasta.ts
OUTPUT      = fasta.js
ARG         = 25000000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
