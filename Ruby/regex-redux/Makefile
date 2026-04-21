LANG        = Ruby
TEST        = regex-redux
SOURCE      = regexredux.yarv-2.yarv
OUTPUT      = regex-redux.rb
ARG         = 21
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/regex-redux.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
