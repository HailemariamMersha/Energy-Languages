LANG    = Java
TEST    = binary-trees
SOURCE  = binarytrees.java-7.java
OUTPUT  = binarytrees.class
ARG     = 21
RUN_CMD = java binarytrees $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) binarytrees.java && $(JAVAC) -d . binarytrees.java

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
