LANG    = Rust
TEST    = spectral-norm
SOURCE  = spectralnorm.rs
OUTPUT  = spectral-norm.rust_run
ARG         = 5500
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = cargo build --release --manifest-path ../Cargo.toml --bin spectral-norm && cp ../target/release/spectral-norm $(OUTPUT)

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
