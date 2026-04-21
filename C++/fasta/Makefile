LANG    = C++
TEST    = fasta
SOURCE  = fasta.gpp-5.c++
OUTPUT  = fasta.gpp_run
ARG     = 11
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++14 -fopenmp

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
