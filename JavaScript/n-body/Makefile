LANG        = JavaScript
TEST        = n-body
SOURCE      = nbody.node
OUTPUT      = n-body.js
ARG         = 50000000
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
