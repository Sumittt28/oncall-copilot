"""Background worker for generating embeddings."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.document import DocumentChunk
from app.services.embeddings import generate_embeddings_batch

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 32
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


async def get_unembedded_chunks(
    db: AsyncSession,
    limit: int = BATCH_SIZE,
) -> list[DocumentChunk]:
    """Get chunks that haven't been embedded yet."""
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.embedding.is_(None))
        .order_by(DocumentChunk.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def embed_chunks(chunks: list[DocumentChunk], db: AsyncSession) -> int:
    """Generate embeddings for a batch of chunks.

    Args:
        chunks: List of DocumentChunk objects to embed.
        db: Database session.

    Returns:
        Number of chunks successfully embedded.
    """
    if not chunks:
        return 0

    # Extract content for batch embedding
    texts = [chunk.content for chunk in chunks]

    try:
        # Generate embeddings
        embeddings = generate_embeddings_batch(texts)

        # Update chunks with embeddings
        now = datetime.now(UTC)
        success_count = 0

        for chunk, embedding in zip(chunks, embeddings, strict=False):
            try:
                chunk.embedding = embedding
                chunk.embedded_at = now
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to set embedding for chunk {chunk.id}: {e}")

        await db.commit()
        return success_count

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        await db.rollback()
        raise


async def process_embedding_queue(max_iterations: int | None = None) -> int:
    """Process pending embeddings in the queue.

    Args:
        max_iterations: Maximum number of batches to process (None for unlimited).

    Returns:
        Total number of chunks embedded.
    """
    total_embedded = 0
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        async with AsyncSessionLocal() as db:
            chunks = await get_unembedded_chunks(db, BATCH_SIZE)

            if not chunks:
                logger.debug("No pending chunks to embed")
                break

            logger.info(f"Processing {len(chunks)} chunks for embedding")

            retries = 0
            while retries < MAX_RETRIES:
                try:
                    embedded = await embed_chunks(chunks, db)
                    total_embedded += embedded
                    logger.info(f"Successfully embedded {embedded} chunks")
                    break
                except Exception as e:
                    retries += 1
                    if retries >= MAX_RETRIES:
                        logger.error(
                            f"Failed to embed chunks after {MAX_RETRIES} retries: {e}"
                        )
                        # Mark these as failed? For now, just skip and continue
                        break
                    logger.warning(
                        f"Embedding retry {retries}/{MAX_RETRIES} after error: {e}"
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        iterations += 1

    return total_embedded


async def embed_document_chunks(document_id: int) -> int:
    """Embed all chunks for a specific document.

    Args:
        document_id: ID of the document to embed.

    Returns:
        Number of chunks embedded.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_(None),
            )
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = list(result.scalars().all())

        if not chunks:
            return 0

        return await embed_chunks(chunks, db)


async def run_embedding_worker(poll_interval: float = 5.0) -> None:
    """Run the embedding worker continuously.

    Args:
        poll_interval: Seconds to wait between polling for new chunks.
    """
    logger.info("Starting embedding worker")

    while True:
        try:
            embedded = await process_embedding_queue(max_iterations=10)
            if embedded > 0:
                logger.info(f"Embedding worker processed {embedded} chunks")
        except Exception as e:
            logger.error(f"Embedding worker error: {e}")

        await asyncio.sleep(poll_interval)
