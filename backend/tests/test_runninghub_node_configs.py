from __future__ import annotations

from app.core.contracts.image_generation import ImageGenerationInput
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub.node_configs import (
    IMAGE_NODE_CONFIGS,
    VIDEO_NODE_CONFIGS,
    ImageNodeConfig,
    VideoNodeConfig,
)


def test_image_node_configs_cover_5_workflows() -> None:
    expected = {
        "2052744677727715329",
        "2003681895185563650",
        "1970396677775499266",
        "2029488621429989377",
        "2058719340626796546",
    }
    assert set(IMAGE_NODE_CONFIGS.keys()) == expected


def test_video_node_configs_cover_4_workflows() -> None:
    expected = {
        "1956699246381469698",
        "2029759632314474498",
        "2055155307592077313",
        "2054820963426021378",
    }
    assert set(VIDEO_NODE_CONFIGS.keys()) == expected


def test_duanju_image_nodes_have_width_height_and_prompt() -> None:
    cfg = IMAGE_NODE_CONFIGS["2052744677727715329"]
    inp = ImageGenerationInput(prompt="a cat", target_ratio="1:1")
    nodes = cfg.build_nodes(inp, None)
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["49"]["fieldName"] == "text"
    assert by_node["49"]["fieldValue"] == "a cat"
    assert by_node["60"]["fieldName"] == "value"
    assert by_node["61"]["fieldName"] == "value"


def test_qwen_image_nodes_include_lora_params() -> None:
    cfg = IMAGE_NODE_CONFIGS["1970396677775499266"]
    inp = ImageGenerationInput(prompt="hero", target_ratio="16:9")
    nodes = cfg.build_nodes(inp, None)
    node_ids = {n["nodeId"] for n in nodes}
    assert {"925", "926", "927", "928", "929"}.issubset(node_ids)
    assert {"931", "932", "887", "860", "938"}.issubset(node_ids)


def test_qwen_edit_nodes_require_image_url() -> None:
    cfg = IMAGE_NODE_CONFIGS["2029488621429989377"]
    assert cfg.requires_image is True
    inp = ImageGenerationInput(prompt="edit this")
    nodes = cfg.build_nodes(inp, "https://rh/img.png")
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["41"]["fieldValue"] == "https://rh/img.png"
    assert by_node["68"]["fieldValue"] == "edit this"


def test_wan22_video_nodes_have_image_prompt_duration_size() -> None:
    cfg = VIDEO_NODE_CONFIGS["1956699246381469698"]
    assert cfg.endpoint == "ai_app"
    assert cfg.image_count == 1
    inp = VideoGenerationInput(prompt="run", ratio="16:9", seconds=5)
    nodes = cfg.build_nodes(inp, "https://rh/img.png")
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["790"]["fieldValue"] == "https://rh/img.png"
    assert by_node["809"]["fieldValue"] == "run"
    assert by_node["789"]["fieldValue"] == "5"
    assert by_node["791"]["fieldValue"] in ("848", "480")


def test_ltx23_standard_video_nodes_use_frames() -> None:
    cfg = VIDEO_NODE_CONFIGS["2029759632314474498"]
    inp = VideoGenerationInput(prompt="dance", ratio="16:9", seconds=5)
    nodes = cfg.build_nodes(inp, "https://rh/img.png")
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["185"]["fieldValue"] == "120"
    assert by_node["224"]["fieldValue"] == "dance"


def test_ltx23_fourframe_uses_workflow_endpoint_and_4_images() -> None:
    cfg = VIDEO_NODE_CONFIGS["2054820963426021378"]
    assert cfg.endpoint == "workflow"
    assert cfg.image_count == 4
    inp = VideoGenerationInput(prompt="flow", ratio="16:9", seconds=5)
    urls = ["https://rh/a.png", "https://rh/b.png", "https://rh/c.png", "https://rh/d.png"]
    nodes = cfg.build_nodes(inp, urls)
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["1361"]["fieldValue"] == "https://rh/a.png"
    assert by_node["1364"]["fieldValue"] == "https://rh/d.png"
    assert by_node["1473"]["fieldValue"] == "flow"
