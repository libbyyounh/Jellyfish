from __future__ import annotations

from app.core.integrations.grsai.image_capabilities import (
    resolve_grsai_image_capability,
)


def test_nano_banana_family_returns_standard_ratios() -> None:
    for model in ("nano-banana", "nano-banana-fast", "nano-banana-pro", "nano-banana-pro-vt"):
        cap = resolve_grsai_image_capability(model)
        assert cap.supports_seed is False
        assert cap.supports_watermark is False
        assert "1:1" in cap.supported_ratios
        assert "16:9" in cap.supported_ratios
        assert "21:9" in cap.supported_ratios
        assert "1:4" not in cap.supported_ratios
        assert "8:1" not in cap.supported_ratios


def test_nano_banana_2_family_returns_extended_ratios() -> None:
    for model in (
        "nano-banana-2",
        "nano-banana-2-cl",
        "nano-banana-2-2k-cl",
        "nano-banana-2-4k-cl",
    ):
        cap = resolve_grsai_image_capability(model)
        assert "1:4" in cap.supported_ratios
        assert "4:1" in cap.supported_ratios
        assert "1:8" in cap.supported_ratios
        assert "8:1" in cap.supported_ratios
        assert "1:1" in cap.supported_ratios


def test_gpt_image_2_family_returns_standard_ratios() -> None:
    for model in ("gpt-image-2", "gpt-image-2-vip"):
        cap = resolve_grsai_image_capability(model)
        assert "1:1" in cap.supported_ratios
        assert "16:9" in cap.supported_ratios
        assert "1:4" not in cap.supported_ratios


def test_unknown_model_returns_default() -> None:
    cap = resolve_grsai_image_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert "1:1" in cap.supported_ratios
