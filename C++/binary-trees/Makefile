LANG    = C++
TEST    = binary-trees
SOURCE  = binarytrees.portable.cpp
OUTPUT  = binary-trees.gpp_run
ARG         = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++17
ifeq (,$(findstring Apple clang,$(shell $(CXX) --version)))
  CXXFLAGS += -fopenmp
endif

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
