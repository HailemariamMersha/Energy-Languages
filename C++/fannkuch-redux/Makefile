LANG    = C++
TEST    = fannkuch-redux
SOURCE  = fannkuchredux.gpp-5.c++
OUTPUT  = fannkuch-redux.gpp_run
ARG     = 11
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++14 -fopenmp

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
