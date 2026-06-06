import pytest
from fastapi import HTTPException

from neuros.llm.registry import get_model
from neuros.llm.selector import select_model
from neuros.main import models_list, query
from neuros.models import QueryInput, TaskType


def test_select_model_accepts_registered_override():
    config = select_model(TaskType.REASONING, "gemma-4-e2b")

    assert config.name == "gemma-4-e2b"
    assert config == get_model("gemma-4-e2b")


def test_select_model_rejects_unknown_override():
    with pytest.raises(ValueError, match="not registered"):
        select_model(TaskType.REASONING, "not-a-model")


@pytest.mark.asyncio
async def test_models_list_hides_endpoint_urls():
    models = await models_list()

    assert models
    assert all("name" in m for m in models)
    assert all("base_url" not in m for m in models)
    assert any(m["default"] for m in models)


@pytest.mark.asyncio
async def test_query_rejects_unknown_model_before_graph():
    with pytest.raises(HTTPException) as exc:
        await query(QueryInput(text="hello", model_name="not-a-model"))

    assert exc.value.status_code == 400
    assert "not registered" in exc.value.detail
