LANG    = Java
TEST    = mandelbrot
SOURCE  = mandelbrot.java-2.java
OUTPUT  = mandelbrot.class
ARG     = 16000
RUN_CMD = java mandelbrot $(ARG)

JAVAC ?= javac

COMPILE_CMD = cp $(SOURCE) mandelbrot.java && $(JAVAC) -d . mandelbrot.java

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
