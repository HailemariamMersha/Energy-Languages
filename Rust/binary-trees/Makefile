LANG    = Rust
TEST    = binary-trees
SOURCE  = binarytrees.rs
OUTPUT  = binary-trees.rust_run
ARG         = 21
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = cargo build --release --manifest-path ../Cargo.toml --bin binary-trees && cp ../target/release/binary-trees $(OUTPUT)

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
