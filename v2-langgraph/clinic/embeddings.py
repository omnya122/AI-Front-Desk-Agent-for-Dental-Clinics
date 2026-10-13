from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .config import get_settings


@lru_cache
def embedder(task_type: str) -> GoogleGenerativeAIEmbeddings:
    """task_type: 'retrieval_document' when indexing, 'retrieval_query' when searching."""
    s = get_settings()
    return GoogleGenerativeAIEmbeddings(
        model=s.embedding_model, task_type=task_type, output_dimensionality=s.embedding_dims
    )
