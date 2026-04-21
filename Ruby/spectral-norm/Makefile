LANG        = Ruby
TEST        = spectral-norm
SOURCE      = spectralnorm.yarv-5.yarv
OUTPUT      = spectral-norm.rb
ARG         = 5500
RUN_CMD     = ruby $(OUTPUT) $(ARG)
COMPILE_CMD = cp $(SOURCE) $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
