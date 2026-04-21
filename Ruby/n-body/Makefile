LANG        = Ruby
TEST        = n-body
SOURCE      = nbody.yarv-2.yarv
OUTPUT      = n-body.rb
ARG         = 50000000
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
