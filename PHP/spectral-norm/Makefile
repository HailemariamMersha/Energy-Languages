LANG        = PHP
TEST        = spectral-norm
SOURCE      = spectralnorm.php
OUTPUT      = spectral-norm.php
ARG         = 5500
RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
