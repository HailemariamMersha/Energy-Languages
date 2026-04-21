LANG    = Rust
TEST    = fannkuch-redux
SOURCE  = fannkuchredux.rs
OUTPUT  = fannkuch-redux.rust_run
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

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
