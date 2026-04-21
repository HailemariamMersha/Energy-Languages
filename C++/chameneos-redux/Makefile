LANG    = C++
TEST    = chameneos-redux
SOURCE  = chameneosredux.gpp-5.c++
OUTPUT  = chameneos-redux.gpp_run
ARG     = 11
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++14 -fopenmp

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

include ../../perfarena.mk
