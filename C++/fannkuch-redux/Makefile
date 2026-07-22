LANG    = C++
TEST    = fannkuch-redux
SOURCE  = fannkuchredux.gpp-5.c++
OUTPUT  = fannkuch-redux.gpp_run
ARG         = 12
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++17
ifeq (,$(findstring Apple clang,$(shell $(CXX) --version)))
  CXXFLAGS += -fopenmp
endif

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
