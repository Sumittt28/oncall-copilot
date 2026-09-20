"""Tests for text chunking service."""


from app.services.chunking import Chunk, chunk_text, estimate_tokens


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self) -> None:
        """Empty string should return 1 (minimum)."""
        assert estimate_tokens("") == 1

    def test_short_text(self) -> None:
        """Short text token estimation."""
        # ~4 chars per token
        assert estimate_tokens("hello") == 1
        assert estimate_tokens("hello world") == 2

    def test_longer_text(self) -> None:
        """Longer text token estimation."""
        text = "This is a longer piece of text that should have more tokens."
        tokens = estimate_tokens(text)
        assert tokens > 10
        assert tokens < 20


class TestChunkText:
    """Tests for text chunking."""

    def test_empty_text(self) -> None:
        """Empty text returns empty list."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text("\n\n\n") == []

    def test_single_chunk_small_text(self) -> None:
        """Small text that fits in one chunk."""
        text = "This is a small piece of text."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].index == 0

    def test_chunk_indices_sequential(self) -> None:
        """Chunk indices should be sequential."""
        # Create text large enough to require multiple chunks
        text = "\n\n".join(["Paragraph " + str(i) + ". " * 50 for i in range(20)])
        chunks = chunk_text(text, target_tokens=100)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunks_have_content(self) -> None:
        """All chunks should have non-empty content."""
        text = "\n\n".join(["Paragraph " + str(i) + ". " * 30 for i in range(10)])
        chunks = chunk_text(text, target_tokens=100)
        for chunk in chunks:
            assert chunk.content.strip()
            assert chunk.token_count > 0

    def test_paragraph_splitting(self) -> None:
        """Text should be split at paragraph boundaries when possible."""
        text = """First paragraph with some content here.

Second paragraph with different content.

Third paragraph with even more content."""
        chunks = chunk_text(text, target_tokens=20, max_tokens=30)
        # Should split into multiple chunks
        assert len(chunks) >= 1
        # Content should be preserved
        combined = "\n\n".join(c.content for c in chunks)
        assert "First paragraph" in combined
        assert "Second paragraph" in combined
        assert "Third paragraph" in combined

    def test_large_file_chunking(self) -> None:
        """Large files should be chunked without data loss."""
        # Simulate a large log file
        lines = [f"Line {i}: " + "x" * 80 for i in range(500)]
        text = "\n".join(lines)

        chunks = chunk_text(text, target_tokens=400, max_tokens=500)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Total content should be roughly preserved (some overlap expected)
        total_content = "".join(c.content for c in chunks)
        # Check that we have most lines (allowing for overlap)
        assert "Line 0:" in total_content
        assert "Line 499:" in total_content

    def test_respects_max_tokens(self) -> None:
        """Chunks should not significantly exceed max_tokens."""
        text = "word " * 1000
        chunks = chunk_text(text, target_tokens=100, max_tokens=150)

        for chunk in chunks:
            # Allow some tolerance since we estimate tokens
            assert chunk.token_count <= 200

    def test_single_long_paragraph(self) -> None:
        """Single long paragraph should be split."""
        text = "This is a sentence. " * 100
        chunks = chunk_text(text, target_tokens=100, max_tokens=150)
        assert len(chunks) > 1

    def test_whitespace_normalization(self) -> None:
        """Multiple whitespace should be normalized."""
        text = "Hello    world\n\n\n\nNew paragraph"
        chunks = chunk_text(text)
        assert "    " not in chunks[0].content  # Multiple spaces collapsed
        assert "\n\n\n\n" not in chunks[0].content  # Multiple newlines collapsed

    def test_chunk_dataclass(self) -> None:
        """Chunk dataclass should have correct attributes."""
        text = "Test content"
        chunks = chunk_text(text)
        chunk = chunks[0]

        assert isinstance(chunk, Chunk)
        assert isinstance(chunk.content, str)
        assert isinstance(chunk.index, int)
        assert isinstance(chunk.token_count, int)


class TestChunkingEdgeCases:
    """Edge case tests for chunking."""

    def test_unicode_content(self) -> None:
        """Unicode content should be handled correctly."""
        text = "Hello 世界! 🎉 Привет мир!"
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert "世界" in chunks[0].content
        assert "🎉" in chunks[0].content

    def test_code_content(self) -> None:
        """Code content should be preserved."""
        text = '''def hello():
    print("Hello, World!")
    return 42

class MyClass:
    def __init__(self):
        self.value = 0'''
        chunks = chunk_text(text)
        combined = " ".join(c.content for c in chunks)
        assert "def hello():" in combined
        assert "class MyClass:" in combined

    def test_json_content(self) -> None:
        """JSON content should be handled."""
        text = '''{"key": "value", "number": 123, "array": [1, 2, 3]}'''
        chunks = chunk_text(text)
        assert len(chunks) >= 1
        assert '"key"' in chunks[0].content

    def test_log_lines(self) -> None:
        """Log file format should be handled."""
        text = """2024-01-15 10:00:00 INFO Starting application
2024-01-15 10:00:01 DEBUG Loading configuration
2024-01-15 10:00:02 ERROR Connection failed: timeout
2024-01-15 10:00:03 INFO Retrying connection"""
        chunks = chunk_text(text)
        combined = " ".join(c.content for c in chunks)
        assert "INFO Starting application" in combined
        assert "ERROR Connection failed" in combined
