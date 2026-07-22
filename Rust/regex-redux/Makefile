LANG    = Rust
TEST    = regex-redux
SOURCE  = regexredux.rs
OUTPUT  = regex-redux.rust_run
ARG         = 0
RUN_CMD = ./$(OUTPUT) $(ARG)

RUSTC       ?= rustc
RUSTC_FLAGS ?= -C opt-level=3 -C lto

ifneq ($(CARGO_BUILD_TARGET),)
  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)
else
  RUSTC_TARGET_FLAG =
endif

COMPILE_CMD = cargo build --release --manifest-path ../Cargo.toml --bin regex-redux && cp ../target/release/regex-redux $(OUTPUT)

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/regex-redux.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
