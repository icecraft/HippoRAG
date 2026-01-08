from .base import EmbeddingConfig, BaseEmbeddingModel
from .OpenAI import OpenAIEmbeddingModel
from .Cohere import CohereEmbeddingModel

from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


def _get_embedding_model_class(embedding_model_name: str = "text-embedding-3-small"):
    if "text-embedding" in embedding_model_name:
        return OpenAIEmbeddingModel
    elif "cohere" in embedding_model_name:
        return CohereEmbeddingModel
    assert False, f"Unknown embedding model name: {embedding_model_name}. Supported models: OpenAI embeddings (text-embedding-*) or Cohere embeddings (cohere.*)"