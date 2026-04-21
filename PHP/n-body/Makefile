LANG        = PHP
TEST        = n-body
SOURCE      = nbody.php-3.php
OUTPUT      = n-body.php
ARG         = 50000000
RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
