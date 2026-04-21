LANG    = Java
TEST    = regex-redux
SOURCE  = regexredux.java-3.java
OUTPUT  = regexredux.class
ARG     = 21
RUN_CMD = java regexredux $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) regexredux.java && $(JAVAC) -d . regexredux.java

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/regex-redux.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
