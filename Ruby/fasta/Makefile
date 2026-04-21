LANG        = Ruby
TEST        = fasta
SOURCE      = fasta.yarv-3.yarv
OUTPUT      = fasta.rb
ARG         = 25000000
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
