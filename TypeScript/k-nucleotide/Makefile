LANG        = TypeScript
TEST        = k-nucleotide
SOURCE      = knucleotide.ts
OUTPUT      = k-nucleotide.js
ARG         = 0
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/k-nucleotide.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
