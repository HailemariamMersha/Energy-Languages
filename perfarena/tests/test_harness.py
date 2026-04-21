"""Tests for the harness's pure logic (no executor calls)."""
from __future__ import annotations

from perfarena.harness import build_env_for


def test_build_env_for_native_x86_cpp():
    env = build_env_for("cpp", "x86_64-linux-gnu")
    assert env["CC"] == "gcc"
    assert env["CXX"] == "g++"


def test_build_env_for_cross_aarch64_cpp():
    env = build_env_for("cpp", "aarch64-linux-gnu")
    assert env["CC"] == "aarch64-linux-gnu-gcc"
    assert env["CXX"] == "aarch64-linux-gnu-g++"


def test_build_env_for_go_sets_goarch_and_goos():
    amd = build_env_for("go", "x86_64-linux-gnu")
    arm = build_env_for("go", "aarch64-linux-gnu")
    assert amd == {"GOOS": "linux", "GOARCH": "amd64", "CGO_ENABLED": "0"}
    assert arm == {"GOOS": "linux", "GOARCH": "arm64", "CGO_ENABLED": "0"}


def test_build_env_for_rust_sets_cargo_target():
    assert build_env_for("rust", "x86_64-linux-gnu") == {
        "CARGO_BUILD_TARGET": "x86_64-unknown-linux-gnu"
    }
    assert build_env_for("rust", "aarch64-linux-gnu") == {
        "CARGO_BUILD_TARGET": "aarch64-unknown-linux-gnu"
    }


def test_build_env_for_arch_independent_languages_is_empty():
    for language in ("python", "java", "csharp", "javascript", "typescript", "php", "ruby"):
        for arch in ("x86_64-linux-gnu", "aarch64-linux-gnu"):
            assert build_env_for(language, arch) == {}


def test_build_env_for_unknown_arch_is_empty():
    assert build_env_for("cpp", "riscv64-linux-gnu") == {}
