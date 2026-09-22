# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Client                                   │
│                         (Next.js Frontend)                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ REST API / SSE
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │   Auth   │ │ Incidents│ │ Documents│ │   RAG    │ │Analytics │   │
│  │   API    │ │   API    │ │   API    │ │   API    │ │   API    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                      Service Layer                             │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │   │
│  │  │Embedding│ │ Search  │ │ Ollama  │ │ GitHub  │ │Postmort.│  │   │
│  │  │ Service │ │ Service │ │ Client  │ │ Client  │ │Generator│  │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────┐
│  PostgreSQL  │ │  Redis   │ │    Ollama    │ │   GitHub     │
│  + pgvector  │ │  Queue   │ │  Local LLM   │ │     API      │
└──────────────┘ └──────────┘ └──────────────┘ └──────────────┘
```

## Data Models

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | Authentication and user profiles |
| `incidents` | Incident records with status/severity |
| `incident_events` | Timeline of incident activities |
| `documents` | Uploaded runbooks, logs, docs |
| `document_chunks` | Chunked document content with embeddings |
| `repositories` | Connected GitHub repositories |
| `ai_investigations` | Stored AI investigation results |
| `incident_evidence` | Cited evidence from investigations |
| `postmortems` | Generated postmortem documents |

### Entity Relationships

```
User (1) ──────────< (N) Incident
                          │
                          ├──< IncidentEvent
                          ├──< Document ──< DocumentChunk
                          ├──< AIInvestigation ──< IncidentEvidence
                          ├──< Postmortem
                          └──< Repository (optional)
```

## RAG Pipeline

### 1. Ingestion

```
Document Upload
      │
      ▼
┌─────────────┐
│   Chunking  │  Split into 300-500 token chunks with overlap
└─────────────┘
      │
      ▼
┌─────────────┐
│  Embedding  │  all-MiniLM-L6-v2 (384 dimensions)
└─────────────┘
      │
      ▼
┌─────────────┐
│   Storage   │  PostgreSQL + pgvector
└─────────────┘
```

### 2. Retrieval

```
Investigation Request
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    Evidence Retrieval                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Attached   │  │  Semantic   │  │   Similar   │            │
│  │  Documents  │  │   Search    │  │  Incidents  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                           │                                    │
│                  ┌────────┴────────┐                          │
│                  ▼                 ▼                          │
│           ┌─────────────┐  ┌─────────────┐                    │
│           │   GitHub    │  │   Commit    │                    │
│           │   Commits   │  │ Correlation │                    │
│           └─────────────┘  └─────────────┘                    │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────┐
│ Merge & Rank  │  Sort by relevance, deduplicate
└───────────────┘
```

### 3. Generation

```
Evidence + Incident
        │
        ▼
┌───────────────┐
│    Prompt     │  System prompt + incident + evidence
│ Construction  │  with explicit citation instructions
└───────────────┘
        │
        ▼
┌───────────────┐
│    Ollama     │  Local LLM (llama3.2:latest)
│   Inference   │  Temperature: 0.3 (factual)
└───────────────┘
        │
        ▼
┌───────────────┐
│    Schema     │  Pydantic validation
│  Validation   │  Retry on failure
└───────────────┘
        │
        ▼
┌───────────────┐
│   Citation    │  Verify all claims have citations
│  Validation   │
└───────────────┘
```

## Security

### Authentication
- JWT-based authentication
- Tokens expire after 24 hours
- Password hashing with bcrypt

### Authorization
- User-scoped data access
- Repository tokens encrypted (TODO: implement encryption)

### API Security
- CORS configuration
- Input validation with Pydantic
- Rate limiting (TODO: implement)

## Performance Considerations

### Database
- pgvector indexes for fast similarity search
- Connection pooling with asyncpg
- Eager loading to avoid N+1 queries

### Caching (TODO)
- Redis for session data
- Document embedding cache
- Search result cache

### Async Processing
- Background embedding generation
- Async database operations
- SSE for streaming AI responses

## Scalability

### Horizontal Scaling
- Stateless backend (easy to scale)
- External session storage (Redis)
- Database connection pooling

### Vertical Scaling
- Ollama model size based on RAM
- Embedding batch processing
- Chunk size tuning

## Monitoring (TODO)

- Health check endpoints
- Prometheus metrics
- Structured logging
- Error tracking (Sentry)

## Deployment

### Development
- Local Python venv
- Docker Compose for services
- Hot reload with uvicorn

### Production
- Docker containers
- Docker Compose orchestration
- Environment-based configuration
- Nginx reverse proxy (optional)
