"""Model selector — routes tasks to the right model."""

from __future__ import annotations

from neuros.config import settings
from neuros.llm.registry import ModelConfig, get_model
from neuros.models import TaskType


def select_model(task: TaskType = TaskType.REASONING) -> ModelConfig:
    """Select the best model for a given task type.

    Routing rules:
        vision    → qwen3-27b (lts1:8000)
        reasoning → qwen3-35b-a3b (lts1:8000)
        fast      → gemma-4 (mac-mini:8001)
    """
    model_name = {
        TaskType.VISION: settings.model_vision,
        TaskType.REASONING: settings.model_fast,
        TaskType.FAST: settings.model_local,
    }.get(task, settings.model_fast)

    config = get_model(model_name)
    if config is None:
        raise ValueError(f"Model '{model_name}' not registered")
    return config
