LANG    = Java
TEST    = fannkuch-redux
SOURCE  = fannkuchredux.java
OUTPUT  = fannkuchredux.class
ARG     = 12
RUN_CMD = java fannkuchredux $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) fannkuchredux.java && $(JAVAC) -d . fannkuchredux.java

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
