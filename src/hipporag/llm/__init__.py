from ..utils.logging_utils import get_logger
from ..utils.config_utils import BaseConfig

from .openai_gpt import CacheOpenAI
from .base import BaseLLM as BaseLLM

__all__ = ["CacheOpenAI", "BaseLLM"]


logger = get_logger(__name__)


def _get_llm_class(config: BaseConfig):
    # All models use OpenAI-compatible interface
    return CacheOpenAI.from_experiment_config(config)
    