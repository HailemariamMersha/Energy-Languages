LANG        = PHP
TEST        = reverse-complement
SOURCE      = revcomp.php-3.php
OUTPUT      = reverse-complement.php
ARG         = 21
RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/reverse-complement.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
