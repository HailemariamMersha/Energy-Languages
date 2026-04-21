LANG    = Java
TEST    = reverse-complement
SOURCE  = revcomp.java-3.java
OUTPUT  = revcomp.class
ARG     = 21
RUN_CMD = java revcomp $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) revcomp.java && $(JAVAC) -d . revcomp.java

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/reverse-complement.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
