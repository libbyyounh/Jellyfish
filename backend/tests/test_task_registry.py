from __future__ import annotations

import pytest

from app.core.task_manager.types import BaseTask
from app.core.tasks.registry import register_task_adapter, resolve_task_adapter


class _DummyTask(BaseTask):
    async def run(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def status(self):
        return {}

    async def is_done(self) -> bool:
        return True

    async def get_result(self):
        return None


class _AnotherDummyTask(BaseTask):
    async def run(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def status(self):
        return {}

    async def is_done(self) -> bool:
        return True

    async def get_result(self):
        return None


def _factory_a(**kwargs) -> BaseTask:  # noqa: ANN003
    return _DummyTask()


def _factory_b(**kwargs) -> BaseTask:  # noqa: ANN003
    return _AnotherDummyTask()


def test_register_task_adapter_is_idempotent_for_same_factory() -> None:
    register_task_adapter("unit_test_kind", "unit_test_provider", _factory_a)
    register_task_adapter("unit_test_kind", "unit_test_provider", _factory_a)

    resolved = resolve_task_adapter("unit_test_kind", "unit_test_provider")
    assert resolved is _factory_a


def test_register_task_adapter_rejects_conflict_factory() -> None:
    register_task_adapter("unit_test_kind_conflict", "unit_test_provider", _factory_a)
    with pytest.raises(ValueError) as exc_info:
        register_task_adapter("unit_test_kind_conflict", "unit_test_provider", _factory_b)
    assert "task adapter conflict" in str(exc_info.value)


def test_resolve_task_adapter_raises_for_unknown_key() -> None:
    with pytest.raises(ValueError) as exc_info:
        resolve_task_adapter("not_registered_kind", "not_registered_provider")
    assert "Unsupported provider/task adapter" in str(exc_info.value)


def test_resolve_provider_key_for_runninghub_aliases() -> None:
    from app.services.llm.provider_registry import resolve_provider_key_from_name
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers

    bootstrap_builtin_providers()
    assert resolve_provider_key_from_name("runninghub") == "runninghub"
    assert resolve_provider_key_from_name("RunningHub") == "runninghub"
    assert resolve_provider_key_from_name("rh") == "runninghub"
    assert resolve_provider_key_from_name("runninghub-personal") == "runninghub"


def test_runninghub_provider_spec_registered() -> None:
    from app.services.llm.provider_registry import get_provider_spec, list_registered_providers
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers
    from app.models.llm import ModelCategoryKey

    bootstrap_builtin_providers()
    spec = get_provider_spec("runninghub")
    assert spec.display_name == "RunningHub"
    assert ModelCategoryKey.image in spec.supported_categories
    assert ModelCategoryKey.video in spec.supported_categories
    assert ModelCategoryKey.text not in spec.supported_categories
    assert spec.default_base_url == "https://www.runninghub.cn"


def test_runninghub_task_adapters_registered() -> None:
    from app.core.tasks.bootstrap import bootstrap_task_adapters
    from app.core.tasks.registry import resolve_task_adapter

    bootstrap_task_adapters()
    image_factory = resolve_task_adapter("image_generation", "runninghub")
    video_factory = resolve_task_adapter("video_generation", "runninghub")
    assert image_factory is not None
    assert video_factory is not None


def test_runninghub_image_task_builds_adapter_impl() -> None:
    from app.core.tasks.image_generation_tasks import ImageGenerationTask, RunningHubImageGenerationTask
    from app.core.contracts.image_generation import ImageGenerationInput
    from app.core.contracts.provider import ProviderConfig

    impl = ImageGenerationTask._build_runninghub_impl(
        provider_config=ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh"),
        input_=ImageGenerationInput(prompt="x", model="2052744677727715329"),
        timeout_s=60.0,
    )
    assert isinstance(impl, RunningHubImageGenerationTask)


def test_runninghub_video_task_builds_adapter_impl() -> None:
    from app.core.tasks.video_generation_tasks import VideoGenerationTask, RunningHubVideoGenerationTask
    from app.core.contracts.video_generation import VideoGenerationInput
    from app.core.contracts.provider import ProviderConfig

    impl = VideoGenerationTask._build_runninghub_impl(
        provider_config=ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh"),
        input_=VideoGenerationInput(prompt="x", ratio="16:9", model="1956699246381469698"),
        poll_interval_s=5.0,
        timeout_s=600.0,
    )
    assert isinstance(impl, RunningHubVideoGenerationTask)


def test_resolve_provider_key_for_runninghub_enterprise_aliases() -> None:
    from app.services.llm.provider_registry import resolve_provider_key_from_name
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers

    bootstrap_builtin_providers()
    assert resolve_provider_key_from_name("runninghub-enterprise") == "runninghub-enterprise"
    assert resolve_provider_key_from_name("RunningHub Enterprise") == "runninghub-enterprise"
    assert resolve_provider_key_from_name("rh-enterprise") == "runninghub-enterprise"


def test_runninghub_enterprise_provider_spec_registered() -> None:
    from app.services.llm.provider_registry import get_provider_spec
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers
    from app.models.llm import ModelCategoryKey

    bootstrap_builtin_providers()
    spec = get_provider_spec("runninghub-enterprise")
    assert spec.display_name == "RunningHub 企业版"
    assert ModelCategoryKey.video in spec.supported_categories
    assert ModelCategoryKey.image not in spec.supported_categories
    assert ModelCategoryKey.text not in spec.supported_categories
    assert spec.default_base_url == "https://www.runninghub.cn"
