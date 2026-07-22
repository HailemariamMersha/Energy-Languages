LANG    = C++
TEST    = pidigits
SOURCE  = pidigits.gpp-4.c++
OUTPUT  = pidigits.gpp_run
ARG         = 10000
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++17
ifeq (,$(findstring Apple clang,$(shell $(CXX) --version)))
  CXXFLAGS += -fopenmp
endif

COMPILE_CMD = $(CXX) $(CXXFLAGS) -I/opt/homebrew/opt/boost/include $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 28
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
