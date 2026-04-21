LANG    = Java
TEST    = pidigits
SOURCE  = pidigits.java-2.java
OUTPUT  = pidigits.class
ARG     = 10000
RUN_CMD = java pidigits $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) pidigits.java && $(JAVAC) -d . pidigits.java

VALIDATION_N       = 27
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
