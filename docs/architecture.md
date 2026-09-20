# Architecture

## System Overview

```
┌─────────────────┐     REST/SSE      ┌─────────────────┐
│    Next.js      │◄──────────────────►│    FastAPI      │
│  React + Tailwind│                    │    Backend      │
└─────────────────┘                    └────────┬────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
          │   PostgreSQL    │         │      Redis      │         │     Ollama      │
          │   + pgvector    │         │   Task Queue    │         │   Local LLM     │
          └─────────────────┘         └────────┬────────┘         └─────────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │ Background      │
                                      │ Worker          │
                                      │ (embeddings)    │
                                      └─────────────────┘
```

## Data Flow

### Incident Investigation

1. User clicks "Investigate with AI" on an incident
2. Backend embeds the incident title + description using sentence-transformers
3. pgvector cosine similarity search retrieves top-k relevant chunks from:
   - Past incidents
   - Runbooks
   - Documentation
4. If a GitHub repo is connected, fetch recent commits/PRs within the time window
5. Merge and deduplicate evidence, assign stable `evidence_id` to each
6. Construct prompt with incident context + labeled evidence
7. Stream response from Ollama via SSE to frontend
8. Validate structured JSON output against Pydantic schema
9. Store investigation in `ai_investigations` table
10. Frontend renders claims with clickable citations

### Document Ingestion

1. User uploads a runbook/log/doc
2. Backend chunks the document (300-500 tokens with overlap)
3. Task queued to Redis for async processing
4. Background worker embeds each chunk with sentence-transformers
5. Chunks + embeddings stored in `document_chunks` with pgvector

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | Authentication, user profiles |
| `incidents` | Incident records with status, severity, ownership |
| `incident_events` | Timeline of incident activity |
| `documents` | Metadata for uploaded runbooks/logs/docs |
| `document_chunks` | Chunked text + vector embeddings |
| `incident_evidence` | Links incidents to relevant evidence chunks |
| `repositories` | Connected GitHub repositories |
| `ai_investigations` | Stored AI analysis with structured output |

### Key Relationships

- `incidents.owner_id` → `users.id`
- `incident_events.incident_id` → `incidents.id`
- `document_chunks.document_id` → `documents.id`
- `incident_evidence.incident_id` → `incidents.id`
- `ai_investigations.incident_id` → `incidents.id`

## API Design

- Base path: `/api/v1/*`
- Authentication: JWT Bearer tokens
- Streaming: SSE at `/api/v1/incidents/{id}/investigate/stream`

### Key Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/signup` | User registration |
| POST | `/auth/login` | JWT token exchange |
| GET | `/incidents` | List incidents |
| POST | `/incidents` | Create incident |
| GET | `/incidents/{id}` | Get incident details |
| PATCH | `/incidents/{id}` | Update incident |
| POST | `/incidents/{id}/investigate` | Trigger AI investigation |
| GET | `/incidents/{id}/investigate/stream` | SSE stream of investigation |
| POST | `/documents` | Upload document |
| GET | `/search` | Semantic search |
| POST | `/incidents/{id}/postmortem` | Generate postmortem |

## AI/RAG Pipeline

### Embedding Model
- `all-MiniLM-L6-v2` via sentence-transformers
- 384-dimensional vectors
- Runs locally, no API calls

### LLM
- Ollama with `llama3.1:8b`
- Runs locally on Apple Silicon
- ~8GB memory footprint

### Structured Output Schema

```json
{
  "summary": "string",
  "severity_estimate": "SEV-1 | SEV-2 | SEV-3 | SEV-4",
  "possible_causes": [
    {"cause": "string", "confidence": 0.0, "evidence_ids": ["string"]}
  ],
  "recommended_actions": ["string"],
  "insufficient_evidence": false
}
```

## Security

- Passwords hashed with bcrypt (passlib)
- JWT tokens with expiration
- All incident endpoints require authentication
- Input validation via Pydantic

## Deviations from Original Plan

*None yet — this document will be updated as the project evolves.*
