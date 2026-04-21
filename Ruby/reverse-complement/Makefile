LANG        = Ruby
TEST        = reverse-complement
SOURCE      = revcomp.yarv-3.yarv
OUTPUT      = reverse-complement.rb
ARG         = 21
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/reverse-complement.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
