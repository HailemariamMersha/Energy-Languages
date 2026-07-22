LANG    = Rust
TEST    = n-body
SOURCE  = nbody.rs
OUTPUT  = n-body.rust_run
ARG         = 50000000
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = cargo build --release --manifest-path ../Cargo.toml --bin n-body && cp ../target/release/n-body $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
