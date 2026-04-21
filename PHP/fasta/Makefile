LANG        = PHP
TEST        = fasta
SOURCE      = fasta.php-3.php
OUTPUT      = fasta.php
ARG         = 25000000
RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
