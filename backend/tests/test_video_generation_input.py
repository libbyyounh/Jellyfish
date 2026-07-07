from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.contracts.video_generation import VideoGenerationInput


def test_accepts_new_optional_fields() -> None:
    inp = VideoGenerationInput(
        prompt="run",
        ratio="16:9",
        reference_frames_base64=["data:image/png;base64,iVBORw0KGgo=", "data:image/png;base64,iVBORw0KGgo="],
        resolution="720P",
        audio=True,
    )
    assert inp.reference_frames_base64 == ["data:image/png;base64,iVBORw0KGgo=", "data:image/png;base64,iVBORw0KGgo="]
    assert inp.resolution == "720P"
    assert inp.audio is True


def test_new_fields_default_none() -> None:
    inp = VideoGenerationInput(prompt="run", ratio="16:9")
    assert inp.reference_frames_base64 is None
    assert inp.resolution is None
    assert inp.audio is None


def test_reference_frames_base64_rejects_non_string_items() -> None:
    with pytest.raises(ValidationError):
        VideoGenerationInput(prompt="run", ratio="16:9", reference_frames_base64=["ok", 123])


def test_reference_frames_base64_counts_as_reference_for_validator() -> None:
    inp = VideoGenerationInput(
        ratio="16:9",
        reference_frames_base64=["data:image/png;base64,iVBORw0KGgo="],
    )
    assert inp.reference_frames_base64 == ["data:image/png;base64,iVBORw0KGgo="]
