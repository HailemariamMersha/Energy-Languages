LANG    = Rust
TEST    = pidigits
SOURCE  = pidigits.rs
OUTPUT  = pidigits.rust_run
ARG         = 10000
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = cargo build --release --manifest-path ../Cargo.toml --bin pidigits && cp ../target/release/pidigits $(OUTPUT)

VALIDATION_N       = 28
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
