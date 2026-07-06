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
async def test_bootstrap_creates_provider_and_9_models(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "runninghub"))).scalar_one()
    assert provider.name == "RunningHub"
    assert provider.base_url == "https://www.runninghub.cn"
    assert provider.status == ProviderStatus.testing

    models = (await db.execute(select(Model).where(Model.provider_id == "runninghub"))).scalars().all()
    assert len(models) == 9
    image_count = sum(1 for m in models if m.category == ModelCategoryKey.image)
    video_count = sum(1 for m in models if m.category == ModelCategoryKey.video)
    assert image_count == 5
    assert video_count == 4


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    models = (await db.execute(select(Model).where(Model.provider_id == "runninghub"))).scalars().all()
    assert len(models) == 9


@pytest.mark.asyncio
async def test_bootstrap_preserves_user_api_key(db: AsyncSession) -> None:
    db.add(Provider(
        id="runninghub",
        name="Old Name",
        base_url="https://custom.rh",
        api_key="user-secret-key",
        api_secret="",
        description="",
        status=ProviderStatus.active,
        created_by="user",
    ))
    await db.commit()

    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "runninghub"))).scalar_one()
    assert provider.api_key == "user-secret-key"
    assert provider.base_url == "https://custom.rh"
    assert provider.status == ProviderStatus.active


@pytest.mark.asyncio
async def test_bootstrap_model_has_workflow_id_in_params(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    model = (await db.execute(
        select(Model).where(Model.id == "runninghub-2052744677727715329")
    )).scalar_one()
    assert model.params["workflow_id"] == "2052744677727715329"
    assert model.params["mode"] == "text"
