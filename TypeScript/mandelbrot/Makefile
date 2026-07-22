LANG        = TypeScript
TEST        = mandelbrot
SOURCE      = mandelbrot.ts
OUTPUT      = mandelbrot.js
ARG         = 16000
RUN_CMD     = node $(OUTPUT) $(ARG)

TSC ?= npx --yes -p typescript@5.9.3 tsc

COMPILE_CMD = $(TSC) --target es2020 --module commonjs --skipLibCheck --outDir . $(SOURCE) && if [ "$(SOURCE:.ts=.js)" != "$(OUTPUT)" ]; then mv $(SOURCE:.ts=.js) $(OUTPUT); fi

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot/typescript.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
