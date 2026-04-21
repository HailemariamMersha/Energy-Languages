LANG        = PHP
TEST        = pidigits
SOURCE      = pidigits.php-5.php
OUTPUT      = pidigits.php
ARG         = 10000
RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 27
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
