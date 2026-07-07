from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base
from app.models.llm import Model, ModelCategoryKey, Provider, ProviderStatus
from app.services.llm.model_bootstrap import bootstrap_builtin_db_resources


async def _build_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return session_local(), engine


@pytest_asyncio.fixture
async def db():
    session, engine = await _build_session()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_creates_grsai_provider_and_13_models(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "grsai"))).scalar_one()
    assert provider.name == "Grsai"
    assert provider.base_url == "https://grsai.dakka.com.cn"
    assert provider.status == ProviderStatus.testing

    models = (await db.execute(select(Model).where(Model.provider_id == "grsai"))).scalars().all()
    assert len(models) == 13
    nano_count = sum(1 for m in models if m.params.get("family") == "nano-banana")
    gpt_count = sum(1 for m in models if m.params.get("family") == "gpt-image-2")
    assert nano_count == 11
    assert gpt_count == 2
    for m in models:
        assert m.category == ModelCategoryKey.image


@pytest.mark.asyncio
async def test_bootstrap_grsai_is_idempotent(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    models = (await db.execute(select(Model).where(Model.provider_id == "grsai"))).scalars().all()
    assert len(models) == 13


@pytest.mark.asyncio
async def test_bootstrap_preserves_grsai_user_api_key(db: AsyncSession) -> None:
    db.add(Provider(
        id="grsai",
        name="Old Name",
        base_url="https://custom.grsai",
        api_key="user-secret-key",
        api_secret="",
        description="",
        status=ProviderStatus.active,
        created_by="user",
    ))
    await db.commit()

    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "grsai"))).scalar_one()
    assert provider.api_key == "user-secret-key"
    assert provider.base_url == "https://custom.grsai"
    assert provider.status == ProviderStatus.active


@pytest.mark.asyncio
async def test_bootstrap_grsai_models_have_family_param(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    nano = (await db.execute(select(Model).where(Model.id == "grsai-nano-banana-2"))).scalar_one()
    assert nano.params["family"] == "nano-banana"
    assert nano.name == "nano-banana-2"

    gpt = (await db.execute(select(Model).where(Model.id == "grsai-gpt-image-2-vip"))).scalar_one()
    assert gpt.params["family"] == "gpt-image-2"
    assert gpt.name == "gpt-image-2-vip"
