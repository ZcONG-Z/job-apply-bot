"""适配器系统的单元测试（无需浏览器）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from job_apply_bot.adapters.base import FieldSpec, load_adapter
from job_apply_bot.adapters.registry import AdapterRegistry, match_url

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_adapter() -> None:
    adapter = load_adapter(FIXTURES / "test-site.yaml")
    assert adapter.site == "test-site"
    assert len(adapter.steps) == 1
    assert len(adapter.steps[0].fields) == 11
    assert adapter.url_patterns == ["*.example.test/*"]


def test_unknown_field_type_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldSpec(key="x", label=["x"], type="not_a_type")


def test_label_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        FieldSpec(key="x", label=[])


def test_site_must_match_filename(tmp_path: Path) -> None:
    target = tmp_path / "foo.yaml"
    target.write_text("site: bar\n", encoding="utf-8")
    with pytest.raises(ValueError, match="foo"):
        load_adapter(target)


def test_broken_adapter_rejected(tmp_path: Path) -> None:
    target = tmp_path / "bad.yaml"
    target.write_text("site: bad\nsteps: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_adapter(target)


class TestMatchUrl:
    def test_full_path_pattern(self) -> None:
        assert match_url(["*.mokahr.com/campus_apply/*"], "https://app.mokahr.com/campus_apply/abc")

    def test_host_only_pattern(self) -> None:
        assert match_url(["app.mokahr.com"], "https://app.mokahr.com/campus_apply/abc")

    def test_no_match(self) -> None:
        assert not match_url(["*.mokahr.com/*"], "https://other.com/x")


class TestRegistry:
    def test_routes_by_url(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(
            "site: a\nmatch:\n  url_patterns: ['*.a.com/*']\nsteps: []\n",
            encoding="utf-8",
        )
        registry = AdapterRegistry(tmp_path)
        registry.load()
        assert registry.find("https://x.a.com/y") is not None
        assert registry.find("https://b.com") is None

    def test_tolerates_broken_adapter(self, tmp_path: Path) -> None:
        (tmp_path / "good.yaml").write_text("site: good\nsteps: []\n", encoding="utf-8")
        (tmp_path / "bad.yaml").write_text("site: bad\nsteps: not-a-list\n", encoding="utf-8")
        registry = AdapterRegistry(tmp_path)
        registry.load()
        assert "good" in registry.names()
        assert "bad.yaml" in registry.errors
