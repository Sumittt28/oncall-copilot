# Model Choice

## LLM: llama3.1:8b via Ollama

### Decision

Selected **Llama 3.1 8B** as the local LLM for AI investigation and postmortem generation.

### Rationale

| Factor | Consideration |
|--------|---------------|
| **Hardware** | MacBook Air M4, 16GB RAM |
| **Memory** | 8B model uses ~5-6GB, leaving headroom for embedding model + system |
| **Performance** | Excellent inference speed on Apple Silicon via Metal |
| **Quality** | Strong instruction-following, good at structured JSON output |
| **Context** | 128K context window (more than enough for evidence + incident) |

### Alternatives Considered

- **gemma2:9b**: Slightly larger, similar quality, but Llama 3.1 has better JSON adherence
- **mistral:7b**: Good but older, Llama 3.1 is more recent and capable
- **llama3.1:70b**: Too large for 16GB RAM
- **phi-3**: Smaller but less capable for complex reasoning

### Installation

```bash
ollama pull llama3.1:8b
```

### Verification

```bash
ollama run llama3.1:8b "Respond with just: OK"
```

## Embedding Model: all-MiniLM-L6-v2

### Decision

Selected **all-MiniLM-L6-v2** from sentence-transformers for document/query embeddings.

### Rationale

| Factor | Consideration |
|--------|---------------|
| **Dimensions** | 384 — compact, fast similarity search |
| **Size** | ~80MB — negligible memory impact |
| **Speed** | ~14,000 sentences/sec on CPU |
| **Quality** | Strong performance on semantic similarity benchmarks |
| **pgvector** | 384 dimensions well-supported |

### Alternatives Considered

- **all-mpnet-base-v2**: Higher quality but 768 dims, larger vectors
- **OpenAI embeddings**: Paid API, violates ₹0 constraint
- **Cohere embeddings**: Paid API

### Installation

```python
pip install sentence-transformers
# Model auto-downloads on first use
```

### Usage

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(["incident description here"])
```

## Performance Notes

- First Ollama request takes ~2-3s (model loading)
- Subsequent requests: ~10-50 tokens/sec depending on context
- Embedding generation: <100ms per chunk
- pgvector similarity search: <50ms for 100K chunks
