"""Smoke tests for config loading."""
from __future__ import annotations

from perfarena.config import load_config


def test_load_config_returns_all_problems_and_languages():
    cfg = load_config()
    assert len(cfg.problems) == 10
    assert len(cfg.languages) == 10


def test_problem_lookup_works_for_all_ten():
    cfg = load_config()
    expected_keys = {
        "binary-trees",
        "fannkuch-redux",
        "fasta",
        "k-nucleotide",
        "mandelbrot",
        "n-body",
        "pidigits",
        "regex-redux",
        "reverse-complement",
        "spectral-norm",
    }
    assert set(cfg.problems) == expected_keys
    for key in expected_keys:
        spec = cfg.get_problem(key)
        assert spec.description.strip()
        assert spec.default_argument


def test_language_lookup_matches_folder_names():
    cfg = load_config()
    expected = {
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "java": "Java",
        "csharp": "CSharp",
        "cpp": "C++",
        "php": "PHP",
        "go": "Go",
        "rust": "Rust",
        "ruby": "Ruby",
    }
    assert set(cfg.languages) == set(expected)
    for key, folder in expected.items():
        assert cfg.get_language(key).folder == folder
