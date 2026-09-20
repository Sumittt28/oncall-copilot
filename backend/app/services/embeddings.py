"""Embedding service using sentence-transformers."""

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Model will be lazy-loaded on first use
_model: Any = None
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


def get_embedding_model() -> "SentenceTransformer":
    """Get or initialize the embedding model (lazy loading)."""
    from sentence_transformers import SentenceTransformer

    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded successfully")
    model: SentenceTransformer = _model
    return model


def generate_embedding(text: str) -> list[float]:
    """Generate embedding for a single text.

    Args:
        text: The text to embed.

    Returns:
        List of floats representing the embedding vector.
    """
    if not text or not text.strip():
        # Return zero vector for empty text
        return [0.0] * EMBEDDING_DIMENSION

    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)

    # Ensure it's a 1D array and convert to list
    if isinstance(embedding, np.ndarray):
        result: list[float] = embedding.flatten().tolist()
        return result

    return [float(x) for x in embedding]


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []

    # Filter empty texts but keep track of indices
    non_empty_indices = []
    non_empty_texts = []
    for i, text in enumerate(texts):
        if text and text.strip():
            non_empty_indices.append(i)
            non_empty_texts.append(text)

    # Generate embeddings for non-empty texts
    results: list[list[float]] = [[0.0] * EMBEDDING_DIMENSION for _ in texts]

    if non_empty_texts:
        model = get_embedding_model()
        embeddings = model.encode(non_empty_texts, convert_to_numpy=True)

        for idx, embedding in zip(non_empty_indices, embeddings, strict=False):
            if isinstance(embedding, np.ndarray):
                results[idx] = embedding.flatten().tolist()
            else:
                results[idx] = list(embedding)

    return results


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity score between -1 and 1.
    """
    a = np.array(vec1)
    b = np.array(vec2)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))
