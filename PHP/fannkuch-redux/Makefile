LANG        = PHP
TEST        = fannkuch-redux
SOURCE      = fannkuchredux.php-3.php
OUTPUT      = fannkuch-redux.php
ARG         = 12
RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
