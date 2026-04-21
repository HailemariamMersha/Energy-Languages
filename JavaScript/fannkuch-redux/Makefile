LANG        = JavaScript
TEST        = fannkuch-redux
SOURCE      = fannkuchredux.node-4.node
OUTPUT      = fannkuch-redux.js
ARG         = 12
RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
