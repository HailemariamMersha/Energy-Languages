LANG    = Rust
TEST    = binary-trees
SOURCE  = binarytrees.rs
OUTPUT  = binary-trees.rust_run
ARG     = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = $(RUSTC) $(RUSTC_FLAGS) $(RUSTC_TARGET_FLAG) $(SOURCE) -o $(OUTPUT)

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
