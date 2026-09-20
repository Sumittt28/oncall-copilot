"""Text chunking service for document processing."""

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    content: str
    index: int
    token_count: int


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple approximation: ~4 characters per token for English text.
    This is a rough estimate; actual tokenization depends on the model.
    """
    return max(1, len(text) // 4)


def chunk_text(
    text: str,
    target_tokens: int = 400,
    min_tokens: int = 100,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Split text into chunks with overlap for RAG retrieval.

    Args:
        text: The text to chunk.
        target_tokens: Target number of tokens per chunk.
        min_tokens: Minimum tokens to form a chunk.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Number of tokens to overlap between chunks.

    Returns:
        List of Chunk objects with content and metadata.
    """
    if not text or not text.strip():
        return []

    # Clean and normalize text
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)  # Collapse multiple newlines
    text = re.sub(r"[ \t]+", " ", text)  # Collapse multiple spaces

    # If text is small enough, return as single chunk
    total_tokens = estimate_tokens(text)
    if total_tokens <= max_tokens:
        return [Chunk(content=text, index=0, token_count=total_tokens)]

    chunks: list[Chunk] = []

    # Split by paragraphs first (double newlines)
    paragraphs = re.split(r"\n\n+", text)

    current_chunk: list[str] = []
    current_tokens = 0
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = estimate_tokens(para)

        # If single paragraph exceeds max, split by sentences
        if para_tokens > max_tokens:
            # Flush current chunk first
            if current_chunk:
                chunk_text_content = "\n\n".join(current_chunk)
                chunks.append(
                    Chunk(
                        content=chunk_text_content,
                        index=chunk_index,
                        token_count=estimate_tokens(chunk_text_content),
                    )
                )
                chunk_index += 1
                current_chunk = []
                current_tokens = 0

            # Split paragraph by sentences
            sentence_chunks = _chunk_by_sentences(
                para, target_tokens, max_tokens, overlap_tokens
            )
            for sc in sentence_chunks:
                sc.index = chunk_index
                chunks.append(sc)
                chunk_index += 1
            continue

        # Check if adding this paragraph would exceed target
        if current_tokens + para_tokens > target_tokens and current_chunk:
            # Save current chunk
            chunk_text_content = "\n\n".join(current_chunk)
            chunks.append(
                Chunk(
                    content=chunk_text_content,
                    index=chunk_index,
                    token_count=estimate_tokens(chunk_text_content),
                )
            )
            chunk_index += 1

            # Start new chunk with overlap
            if overlap_tokens > 0 and current_chunk:
                # Keep last paragraph for overlap if it fits
                last_para = current_chunk[-1]
                if estimate_tokens(last_para) <= overlap_tokens:
                    current_chunk = [last_para]
                    current_tokens = estimate_tokens(last_para)
                else:
                    current_chunk = []
                    current_tokens = 0
            else:
                current_chunk = []
                current_tokens = 0

        current_chunk.append(para)
        current_tokens += para_tokens

    # Don't forget the last chunk
    if current_chunk:
        chunk_text_content = "\n\n".join(current_chunk)
        token_count = estimate_tokens(chunk_text_content)
        # Only add if it meets minimum or is the only content
        if token_count >= min_tokens or not chunks:
            chunks.append(
                Chunk(
                    content=chunk_text_content,
                    index=chunk_index,
                    token_count=token_count,
                )
            )
        elif chunks:
            # Append to previous chunk if too small
            prev_chunk = chunks[-1]
            combined = prev_chunk.content + "\n\n" + chunk_text_content
            chunks[-1] = Chunk(
                content=combined,
                index=prev_chunk.index,
                token_count=estimate_tokens(combined),
            )

    return chunks


def _chunk_by_sentences(
    text: str,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Split text by sentences when paragraphs are too large."""
    # Simple sentence splitting (handles common cases)
    sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z])"
    sentences = re.split(sentence_pattern, text)

    chunks: list[Chunk] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_tokens = estimate_tokens(sentence)

        # Single sentence exceeds max - split by words
        if sentence_tokens > max_tokens:
            if current_sentences:
                chunk_content = " ".join(current_sentences)
                chunks.append(
                    Chunk(
                        content=chunk_content,
                        index=len(chunks),
                        token_count=estimate_tokens(chunk_content),
                    )
                )
                current_sentences = []
                current_tokens = 0

            # Split long sentence by words
            word_chunks = _chunk_by_words(sentence, target_tokens, max_tokens)
            chunks.extend(word_chunks)
            continue

        if current_tokens + sentence_tokens > target_tokens and current_sentences:
            chunk_content = " ".join(current_sentences)
            chunks.append(
                Chunk(
                    content=chunk_content,
                    index=len(chunks),
                    token_count=estimate_tokens(chunk_content),
                )
            )

            # Overlap: keep last sentence if small enough
            if overlap_tokens > 0 and current_sentences:
                last = current_sentences[-1]
                if estimate_tokens(last) <= overlap_tokens:
                    current_sentences = [last]
                    current_tokens = estimate_tokens(last)
                else:
                    current_sentences = []
                    current_tokens = 0
            else:
                current_sentences = []
                current_tokens = 0

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    if current_sentences:
        chunk_content = " ".join(current_sentences)
        chunks.append(
            Chunk(
                content=chunk_content,
                index=len(chunks),
                token_count=estimate_tokens(chunk_content),
            )
        )

    return chunks


def _chunk_by_words(text: str, target_tokens: int, max_tokens: int) -> list[Chunk]:
    """Last resort: split by words for very long text without structure."""
    words = text.split()
    chunks: list[Chunk] = []
    current_words: list[str] = []
    current_tokens = 0

    for word in words:
        word_tokens = estimate_tokens(word)

        if current_tokens + word_tokens > target_tokens and current_words:
            chunk_content = " ".join(current_words)
            chunks.append(
                Chunk(
                    content=chunk_content,
                    index=len(chunks),
                    token_count=estimate_tokens(chunk_content),
                )
            )
            current_words = []
            current_tokens = 0

        current_words.append(word)
        current_tokens += word_tokens

    if current_words:
        chunk_content = " ".join(current_words)
        chunks.append(
            Chunk(
                content=chunk_content,
                index=len(chunks),
                token_count=estimate_tokens(chunk_content),
            )
        )

    return chunks
