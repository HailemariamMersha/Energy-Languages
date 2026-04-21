LANG    = Rust
TEST    = mandelbrot
SOURCE  = mandelbrot.rs
OUTPUT  = mandelbrot.rust_run
ARG     = 16
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = $(RUSTC) $(RUSTC_FLAGS) $(RUSTC_TARGET_FLAG) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
