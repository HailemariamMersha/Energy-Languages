LANG    = C++
TEST    = mandelbrot
SOURCE  = mandelbrot.portable.cpp
OUTPUT  = mandelbrot.gpp_run
ARG         = 16000
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++17
ifeq (,$(findstring Apple clang,$(shell $(CXX) --version)))
  CXXFLAGS += -fopenmp
endif

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot/cpp.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
