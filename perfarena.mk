# perfarena.mk
#
# Common include for PerfArena benchmark Makefiles.
#
# Each per-benchmark Makefile sets a small number of variables
# describing the cell, then includes this file. See GUIDE.md for
# the full list of variables and what they mean.
#
# Variables:
#
#   LANG            Language folder name (Python, C++, Java, ...).
#   TEST            CLBG problem key (binary-trees, n-body, ...).
#   SOURCE          Canonical source file in this cell.
#   OUTPUT          Artifact produced by `make compile`.
#   ARG             Default N argument for measurement runs.
#   RUN_CMD         Command to invoke the benchmark at the default N.
#   COMPILE_CMD     Command to produce OUTPUT from SOURCE.
#
# Stdin-input problems (k-nucleotide, regex-redux, reverse-complement)
# also set:
#
#   STDIN_FILE      Path to the pre-generated input file (relative
#                   to the cell, typically ../../reference/inputs/...).
#
# When STDIN_FILE is set, the run/measure/validate targets pipe it
# into the benchmark automatically, so the harness and RAPL runner
# see a uniform command regardless of whether the problem reads
# from argv or stdin.
#
# Validation:
#
#   VALIDATION_N    Small N for the correctness check (runs in <1 s).
#   REFERENCE_OUTPUT  Path to the expected output at VALIDATION_N.
#   BINARY_OUTPUT   Set to 1 for mandelbrot (cmp instead of diff).
#
# The harness exports CC, CXX, CARGO_BUILD_TARGET, GOOS, GOARCH
# when cross-compiling. Per-language COMPILE_CMDs should use $(CC),
# $(CXX), etc. rather than hardcoded paths.

PERFARENA_WARMUP  ?= 10
PERFARENA_MEASURE ?= 20
PERFARENA_IDLE_S  ?= 5

# Auto-detect the measurement runner.
#   Linux with the RAPL runner built:  use the C binary (direct MSR, 10 Hz).
#   macOS or Linux without RAPL:       use the Python CodeCarbon runner.
# Override with: make measure PERFARENA_RUNNER=...
_RAPL_RUNNER   = ../../RAPL/perfarena_runner
_CC_RUNNER     = python3 -m perfarena.runners.codecarbon_runner

ifeq ($(shell uname -s),Darwin)
  PERFARENA_RUNNER  ?= $(_CC_RUNNER)
else ifeq ($(wildcard $(_RAPL_RUNNER)),)
  PERFARENA_RUNNER  ?= $(_CC_RUNNER)
else
  PERFARENA_RUNNER  ?= $(_RAPL_RUNNER)
endif

CC  ?= gcc
CXX ?= g++

VALIDATION_N       ?=
REFERENCE_OUTPUT   ?=
BINARY_OUTPUT      ?= 0

# Build the full run command, appending stdin redirect if needed.
ifdef STDIN_FILE
  _FULL_RUN_CMD = $(RUN_CMD) < $(STDIN_FILE)
  _FULL_VALIDATE_CMD = $(subst $(ARG),$(VALIDATION_N),$(RUN_CMD)) < $(STDIN_FILE)
else
  _FULL_RUN_CMD = $(RUN_CMD)
  _FULL_VALIDATE_CMD = $(subst $(ARG),$(VALIDATION_N),$(RUN_CMD))
endif

.PHONY: compile run measure mem validate clean

compile:
	$(COMPILE_CMD)

run:
	$(RUN_CMD)

measure:
ifeq ($(shell uname -s),Darwin)
	$(PERFARENA_RUNNER) "$(_FULL_RUN_CMD)" $(LANG) $(TEST) $(PERFARENA_WARMUP) $(PERFARENA_MEASURE) $(PERFARENA_IDLE_S)
else
	@if echo "$(PERFARENA_RUNNER)" | grep -q "perfarena_runner$$" && [ ! -x $(PERFARENA_RUNNER) ]; then \
	    echo "perfarena.mk: $(PERFARENA_RUNNER) is missing; build RAPL/ first" >&2 ; \
	    exit 1 ; \
	fi
	sudo modprobe msr || true
	sudo $(PERFARENA_RUNNER) "$(_FULL_RUN_CMD)" $(LANG) $(TEST) $(PERFARENA_WARMUP) $(PERFARENA_MEASURE) $(PERFARENA_IDLE_S)
endif

mem:
	/usr/bin/time -v $(_FULL_RUN_CMD)

# Correctness oracle: run the benchmark at a small N and compare
# output against the reference. Measurement should be gated behind
# this step.
validate:
	@if [ -z "$(REFERENCE_OUTPUT)" ]; then \
	    echo "validate: REFERENCE_OUTPUT is not set for $(LANG)/$(TEST)" >&2 ; \
	    exit 1 ; \
	fi
	@echo "validate: running $(TEST) at N=$(VALIDATION_N)..."
	@$(_FULL_VALIDATE_CMD) > /tmp/_perfarena_validate_actual.out 2>/dev/null
	@if [ "$(BINARY_OUTPUT)" = "1" ]; then \
	    cmp -s /tmp/_perfarena_validate_actual.out $(REFERENCE_OUTPUT) ; \
	else \
	    diff -q /tmp/_perfarena_validate_actual.out $(REFERENCE_OUTPUT) > /dev/null ; \
	fi && echo "validate: PASS" || { echo "validate: FAIL (output differs from $(REFERENCE_OUTPUT))" >&2 ; exit 1 ; }
	@rm -f /tmp/_perfarena_validate_actual.out

clean:
	rm -f $(OUTPUT)
