LANG        = Ruby
TEST        = pidigits
SOURCE      = pidigits.yarv-5.yarv
OUTPUT      = pidigits.rb
ARG         = 10000
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 27
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
