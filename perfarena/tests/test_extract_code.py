"""Tests for the code-extraction logic in the generation pipeline."""
from __future__ import annotations

from perfarena.generation.pipeline import extract_code


def test_extract_code_prefers_language_tagged_block():
    raw = (
        "Here you go:\n"
        "```python\n"
        "print('hello')\n"
        "```\n"
        "and also\n"
        "```text\n"
        "not code\n"
        "```\n"
    )
    assert "print('hello')" in extract_code(raw, "python")
    assert "not code" not in extract_code(raw, "python")


def test_extract_code_falls_back_to_any_fenced_block():
    raw = "```\nprint('hi')\n```\n"
    assert "print('hi')" in extract_code(raw, "python")


def test_extract_code_language_aliases_work():
    raw = "```js\nconsole.log(1)\n```"
    assert "console.log(1)" in extract_code(raw, "javascript")
    raw_cpp = "```cpp\nint main(){}\n```"
    assert "int main(){}" in extract_code(raw_cpp, "cpp")
    raw_csharp = "```cs\nclass A {}\n```"
    assert "class A {}" in extract_code(raw_csharp, "csharp")


def test_extract_code_returns_raw_if_no_fence():
    raw = "int main(){ return 0; }"
    assert extract_code(raw, "cpp").strip() == raw.strip()
