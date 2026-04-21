# PerfArena build container.
#
# This image is a BUILD ENVIRONMENT, not an execution environment.
# It carries the toolchains needed to compile the 10 PerfArena target
# languages for a specified CPU architecture (native x86_64 or
# cross-compiled to aarch64). Measurement always happens on a remote
# host (the bare-metal reference machine), reached over SSH by the
# perfarena CLI. This container never runs `perf`, `make measure`,
# or any measurement command itself.
#
# Responsibilities of this container:
#   1. Run the LLM generation pipeline and write source files to disk.
#   2. Compile / transpile those source files for the target arch.
#   3. Ship the built artifacts to the remote host via SFTP.
#   4. Ask the remote host to run them and return the measurements.
#
# Target arch selection:
#   - "auto"              probes the remote host via `uname -m`
#   - "x86_64-linux-gnu"  native build on this image
#   - "aarch64-linux-gnu" cross-compile using gcc-aarch64-linux-gnu,
#                         rustup target aarch64-unknown-linux-gnu,
#                         and GOARCH=arm64 for Go
#
# Build:   docker build -t perfarena:latest .
# Run:     docker run --rm -it \
#              -v "$PWD":/workspace \
#              -v ~/.ssh:/root/.ssh:ro \
#              -e OPENAI_API_KEY -e ANTHROPIC_API_KEY -e GOOGLE_API_KEY \
#              perfarena:latest --help

FROM ubuntu:24.04

# Provenance build-args. Pass `docker build --build-arg
# PERFARENA_GIT_SHA=$(git rev-parse HEAD) --build-arg
# PERFARENA_IMAGE_TAG=perfarena:$(date +%Y%m%d)` so every
# subsequent run can read the image identity from the environment.
ARG PERFARENA_GIT_SHA=unknown
ARG PERFARENA_IMAGE_TAG=unknown
ARG PERFARENA_BUILD_DATE=unknown

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PERFARENA_GIT_SHA=${PERFARENA_GIT_SHA} \
    PERFARENA_IMAGE_TAG=${PERFARENA_IMAGE_TAG} \
    PERFARENA_BUILD_DATE=${PERFARENA_BUILD_DATE}

# Core system tools. No `perf`, no `linux-tools-*`: measurement lives
# on the remote host.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget git make build-essential pkg-config \
        openssh-client rsync \
    && rm -rf /var/lib/apt/lists/*

# Native and cross-compile C/C++ toolchains.
#   - gcc / g++:                       native x86_64 host build
#   - gcc-aarch64-linux-gnu / g++...:  cross-compile to aarch64 Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ clang \
        gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
    && rm -rf /var/lib/apt/lists/*

# Arch-independent compilers / transpilers.
#   Java:    javac produces .class bytecode (arch-independent).
#   .NET:    dotnet build produces IL (arch-independent), with optional
#            RID-specific publish for native AOT.
#   Node:    required to run tsc (arch-independent).
#   Python:  required to run the perfarena CLI and the generation
#            pipeline itself.
#   PHP:     interpreter for syntax-check-before-ship.
#   Ruby:    interpreter for syntax-check-before-ship.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv python3-dev \
        openjdk-21-jdk-headless \
        dotnet-sdk-8.0 \
        nodejs npm \
        php-cli \
        ruby \
    && rm -rf /var/lib/apt/lists/*

# TypeScript compiler (tsc) and ts-node.
RUN npm install -g typescript ts-node

# Go. Cross-compilation works out of the box via GOARCH/GOOS
# environment variables, no extra toolchains required.
RUN apt-get update && apt-get install -y --no-install-recommends \
        golang-go \
    && rm -rf /var/lib/apt/lists/*

# Rust via rustup, with cross-compile targets for both supported
# architectures. PATH is updated so later layers and runtime both see
# the cargo and rustup binaries.
ENV CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    PATH=/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --default-toolchain stable --profile minimal \
          --no-modify-path \
    && rustup target add x86_64-unknown-linux-gnu \
    && rustup target add aarch64-unknown-linux-gnu

# Capture every toolchain version once, at image build time, into a
# single file. The perfarena harness reads it per run so that every
# measurement row can record the exact toolchain that produced its
# binary (proposal Section 4 item 3, language-vs-implementation).
RUN { \
      echo "build_date=$(date -Iseconds)"; \
      echo "image=perfarena-build"; \
      echo "git_sha=${PERFARENA_GIT_SHA}"; \
      echo "image_tag=${PERFARENA_IMAGE_TAG}"; \
      echo "build_arg_date=${PERFARENA_BUILD_DATE}"; \
      gcc --version | head -1; \
      g++ --version | head -1; \
      aarch64-linux-gnu-gcc --version | head -1; \
      aarch64-linux-gnu-g++ --version | head -1; \
      clang --version | head -1; \
      python3 --version; \
      node --version; \
      (tsc --version || true); \
      javac -version 2>&1 | head -1; \
      dotnet --version; \
      php --version | head -1; \
      ruby --version; \
      go version; \
      rustc --version; \
      cargo --version; \
    } > /etc/perfarena-versions

WORKDIR /workspace

# Install the perfarena Python package itself.
COPY pyproject.toml /src/perfarena/pyproject.toml
COPY perfarena /src/perfarena/perfarena
RUN pip install --break-system-packages --no-cache-dir /src/perfarena

# The installed entry point drives the CLI against the fork that the
# caller bind-mounts at /workspace.
ENTRYPOINT ["perfarena"]
CMD ["--help"]
