LANG    = Rust
TEST    = fasta
SOURCE  = fasta.rs
OUTPUT  = fasta.rust_run
ARG         = 25000000
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = cargo build --release --manifest-path ../Cargo.toml --bin fasta && cp ../target/release/fasta $(OUTPUT)

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
