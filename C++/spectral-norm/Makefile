LANG    = C++
TEST    = spectral-norm
SOURCE  = spectralnorm.portable.cpp
OUTPUT  = spectral-norm.gpp_run
ARG         = 5500
RUN_CMD = ./$(OUTPUT) $(ARG)

CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++17
ifeq (,$(findstring Apple clang,$(shell $(CXX) --version)))
  CXXFLAGS += -fopenmp
endif

COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
