"""Tests for embedding service."""


from app.services.embeddings import (
    EMBEDDING_DIMENSION,
    cosine_similarity,
    generate_embedding,
    generate_embeddings_batch,
)


class TestGenerateEmbedding:
    """Tests for single embedding generation."""

    def test_empty_text_returns_zero_vector(self) -> None:
        """Empty text should return zero vector."""
        embedding = generate_embedding("")
        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(v == 0.0 for v in embedding)

    def test_whitespace_only_returns_zero_vector(self) -> None:
        """Whitespace-only text should return zero vector."""
        embedding = generate_embedding("   \n\t  ")
        assert len(embedding) == EMBEDDING_DIMENSION
        assert all(v == 0.0 for v in embedding)

    def test_returns_correct_dimension(self) -> None:
        """Embedding should have correct dimension."""
        embedding = generate_embedding("Hello, world!")
        assert len(embedding) == EMBEDDING_DIMENSION

    def test_returns_list_of_floats(self) -> None:
        """Embedding should be a list of floats."""
        embedding = generate_embedding("Test text")
        assert isinstance(embedding, list)
        assert all(isinstance(v, float) for v in embedding)

    def test_similar_texts_have_high_similarity(self) -> None:
        """Similar texts should have similar embeddings."""
        emb1 = generate_embedding("The database connection timed out")
        emb2 = generate_embedding("Database connection timeout error")
        similarity = cosine_similarity(emb1, emb2)
        assert similarity > 0.7  # Should be quite similar

    def test_different_texts_have_lower_similarity(self) -> None:
        """Different texts should have different embeddings."""
        emb1 = generate_embedding("The database connection timed out")
        emb2 = generate_embedding("The weather is sunny today")
        similarity = cosine_similarity(emb1, emb2)
        assert similarity < 0.5  # Should be quite different

    def test_identical_texts_have_similarity_one(self) -> None:
        """Identical texts should have similarity of 1."""
        text = "The quick brown fox"
        emb1 = generate_embedding(text)
        emb2 = generate_embedding(text)
        similarity = cosine_similarity(emb1, emb2)
        assert abs(similarity - 1.0) < 0.001


class TestGenerateEmbeddingsBatch:
    """Tests for batch embedding generation."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty input should return empty list."""
        result = generate_embeddings_batch([])
        assert result == []

    def test_batch_returns_correct_count(self) -> None:
        """Batch should return same number of embeddings as inputs."""
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = generate_embeddings_batch(texts)
        assert len(embeddings) == 3

    def test_batch_handles_empty_strings(self) -> None:
        """Batch should handle empty strings."""
        texts = ["Valid text", "", "Another text"]
        embeddings = generate_embeddings_batch(texts)
        assert len(embeddings) == 3
        # Empty string should have zero vector
        assert all(v == 0.0 for v in embeddings[1])
        # Non-empty should have non-zero vectors
        assert any(v != 0.0 for v in embeddings[0])
        assert any(v != 0.0 for v in embeddings[2])

    def test_batch_preserves_order(self) -> None:
        """Batch should preserve order of inputs."""
        texts = ["Database error", "Weather forecast", "Network issue"]
        embeddings = generate_embeddings_batch(texts)

        # First and third should be more similar (tech topics)
        sim_1_3 = cosine_similarity(embeddings[0], embeddings[2])
        sim_1_2 = cosine_similarity(embeddings[0], embeddings[1])
        assert sim_1_3 > sim_1_2


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors(self) -> None:
        """Identical vectors should have similarity of 1."""
        vec = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 0.001

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors should have similarity of 0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(vec1, vec2)) < 0.001

    def test_opposite_vectors(self) -> None:
        """Opposite vectors should have similarity of -1."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        assert abs(cosine_similarity(vec1, vec2) + 1.0) < 0.001

    def test_zero_vector(self) -> None:
        """Zero vector should return 0 similarity."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec1, vec2) == 0.0


class TestSemanticSimilarity:
    """Tests for semantic understanding of embeddings."""

    def test_paraphrase_similarity(self) -> None:
        """Paraphrased text should be similar."""
        original = "The server crashed due to memory issues"
        paraphrase = "Memory problems caused the server to crash"
        emb1 = generate_embedding(original)
        emb2 = generate_embedding(paraphrase)
        similarity = cosine_similarity(emb1, emb2)
        assert similarity > 0.6

    def test_technical_terms_cluster(self) -> None:
        """Related technical terms should cluster together."""
        db_error = generate_embedding("PostgreSQL database connection error")
        db_timeout = generate_embedding("MySQL query timeout exception")
        weather = generate_embedding("Sunny weather forecast for tomorrow")

        sim_db = cosine_similarity(db_error, db_timeout)
        sim_other = cosine_similarity(db_error, weather)

        # Database terms should be more similar to each other
        assert sim_db > sim_other

    def test_incident_description_similarity(self) -> None:
        """Similar incident descriptions should match."""
        inc1 = "Users reporting slow page load times on the checkout page"
        inc2 = "Checkout page is loading slowly for customers"
        inc3 = "New feature deployment completed successfully"

        emb1 = generate_embedding(inc1)
        emb2 = generate_embedding(inc2)
        emb3 = generate_embedding(inc3)

        sim_related = cosine_similarity(emb1, emb2)
        sim_unrelated = cosine_similarity(emb1, emb3)

        assert sim_related > 0.7
        assert sim_unrelated < 0.5

    def test_error_message_similarity(self) -> None:
        """Similar error messages should be detected."""
        err1 = "ConnectionRefusedError: Connection to database refused"
        err2 = "Database connection was refused by the server"
        err3 = "File not found: /var/log/app.log"

        emb1 = generate_embedding(err1)
        emb2 = generate_embedding(err2)
        emb3 = generate_embedding(err3)

        sim_related = cosine_similarity(emb1, emb2)
        sim_unrelated = cosine_similarity(emb1, emb3)

        assert sim_related > sim_unrelated

    def test_runbook_content_similarity(self) -> None:
        """Similar runbook procedures should match."""
        step1 = "First, check the database connection status"
        step2 = "Verify that the database is connected properly"
        step3 = "Deploy the new container to production"

        emb1 = generate_embedding(step1)
        emb2 = generate_embedding(step2)
        emb3 = generate_embedding(step3)

        assert cosine_similarity(emb1, emb2) > cosine_similarity(emb1, emb3)
