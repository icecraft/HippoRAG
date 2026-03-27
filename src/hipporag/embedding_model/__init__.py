from .base import EmbeddingConfig as EmbeddingConfig
from .base import BaseEmbeddingModel as BaseEmbeddingModel
from .OpenAI import OpenAIEmbeddingModel

__all__ = ["EmbeddingConfig", "BaseEmbeddingModel", "OpenAIEmbeddingModel"]

from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


def _get_embedding_model_class(embedding_model_name: str = "text-embedding-3-small"):
    if "text-embedding" in embedding_model_name:
        return OpenAIEmbeddingModel
    assert False, f"Unknown embedding model name: {embedding_model_name}. Supported models: OpenAI-compatible embeddings (text-embedding-*)"