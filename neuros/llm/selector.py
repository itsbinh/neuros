"""Model selector — routes tasks to the right model."""

from __future__ import annotations

from neuros.config import settings
from neuros.llm.registry import ModelConfig, get_model
from neuros.models import TaskType


def select_model(task: TaskType = TaskType.REASONING, model_name: str | None = None) -> ModelConfig:
    """Select the best model for a given task type.

    Routing rules:
        vision    → qwen3-27b (lts1:8000)
        reasoning → qwen3-35b-a3b (lts1:8000)
        fast      → gemma-4 (mac-mini:8001)
    """
    if model_name is None:
        model_name = {
            TaskType.VISION: settings.model_vision,
            TaskType.REASONING: settings.model_fast,
            TaskType.FAST: settings.model_local,
        }.get(task, settings.model_fast)

    config = get_model(model_name)
    if config is None:
        raise ValueError(f"Model '{model_name}' not registered")
    if task != TaskType.VISION and "text" not in config.capabilities:
        raise ValueError(f"Model '{model_name}' does not support text")
    if task == TaskType.VISION and "vision" not in config.capabilities:
        raise ValueError(f"Model '{model_name}' does not support vision")
    return config
