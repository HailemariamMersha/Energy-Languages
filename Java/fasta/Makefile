LANG    = Java
TEST    = fasta
SOURCE  = fasta.java-5.java
OUTPUT  = fasta.class
ARG     = 25000000
RUN_CMD = java fasta $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) fasta.java && $(JAVAC) -d . fasta.java

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
