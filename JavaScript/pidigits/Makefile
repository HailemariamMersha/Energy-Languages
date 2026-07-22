LANG        = JavaScript
TEST        = pidigits
SOURCE      = pidigits.js
OUTPUT      = pidigits.run.js
ARG         = 10000
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 28
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
