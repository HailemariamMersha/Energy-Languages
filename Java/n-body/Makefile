LANG    = Java
TEST    = n-body
SOURCE  = nbody.java-4.java
OUTPUT  = nbody.class
ARG     = 50000000
RUN_CMD = java nbody $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) nbody.java && $(JAVAC) -d . nbody.java

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
