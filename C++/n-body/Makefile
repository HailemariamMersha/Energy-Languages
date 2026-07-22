LANG    = C++
TEST    = n-body
SOURCE  = nbody.portable.cpp
OUTPUT  = n-body.gpp_run
ARG         = 50000000
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++17
ifeq (,$(findstring Apple clang,$(shell $(CXX) --version)))
  CXXFLAGS += -fopenmp
endif

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
