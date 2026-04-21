LANG        = Ruby
TEST        = fannkuch-redux
SOURCE      = fannkuchredux.yarv-2.yarv
OUTPUT      = fannkuch-redux.rb
ARG         = 12
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
