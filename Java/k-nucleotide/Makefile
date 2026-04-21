LANG    = Java
TEST    = k-nucleotide
SOURCE  = knucleotide.java
OUTPUT  = knucleotide.class
ARG     = 12
RUN_CMD = java knucleotide $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) knucleotide.java && $(JAVAC) -d . knucleotide.java

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/k-nucleotide.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
