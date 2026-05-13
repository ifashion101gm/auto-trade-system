"""Overall functionality smoke tests for the trading system.

These tests intentionally avoid network, exchange credentials, and database
connections. They validate that core source files are syntactically loadable and
that foundational optimization assumptions stay true.
"""
from __future__ import annotations

import py_compile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def iter_python_sources(*roots: str):
    for root in roots:
        yield from sorted((PROJECT_ROOT / root).rglob("*.py"))


def test_application_and_test_sources_compile():
    """Compile app and test code to catch broad syntax regressions early."""
    failures: list[str] = []

    for source in iter_python_sources("app", "tests"):
        try:
            py_compile.compile(str(source), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{source.relative_to(PROJECT_ROOT)}: {exc.msg}")

    assert not failures, "Python syntax failures:\n" + "\n".join(failures)


def test_pytest_collection_is_limited_to_maintained_tests():
    """Ensure ad-hoc validation scripts are not collected as unit tests."""
    config = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "testpaths = tests" in config
    assert "python_files = test_*.py" in config
