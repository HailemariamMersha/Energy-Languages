LANG    = Java
TEST    = spectral-norm
SOURCE  = spectralnorm.java-2.java
OUTPUT  = spectralnorm.class
ARG     = 5500
RUN_CMD = java spectralnorm $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) spectralnorm.java && $(JAVAC) -d . spectralnorm.java

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
