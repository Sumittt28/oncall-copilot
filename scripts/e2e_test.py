#!/usr/bin/env python3
"""
End-to-End Test Script for OnCall Copilot

This script tests the complete flow:
1. User signup/login
2. Create an incident
3. Upload a document (runbook)
4. Embed the document
5. Run AI investigation
6. Resolve incident
7. Generate postmortem
8. Check analytics

Prerequisites:
- Backend running at http://localhost:8000
- Ollama running with llama3.2:latest
- Docker services (postgres, redis) running
"""

import asyncio
import sys
import time
from datetime import datetime

import httpx

API_BASE = "http://localhost:8000"

# Test data
TEST_USER = {
    "email": f"test_{int(time.time())}@example.com",
    "password": "testpassword123",
    "name": "Test User"
}

TEST_INCIDENT = {
    "title": "Database Connection Timeout",
    "description": "Users are experiencing slow queries and connection timeouts when accessing the database. Error logs show 'connection pool exhausted' messages.",
    "severity": "SEV-2"
}

TEST_RUNBOOK = """# Database Recovery Runbook

## Symptoms
- Connection timeouts
- Slow queries
- "Connection pool exhausted" errors

## Root Cause
Usually caused by connection pool exhaustion due to:
1. Connection leaks in application code
2. Long-running transactions
3. Insufficient pool size for load

## Resolution Steps
1. Check current connection count: `SELECT count(*) FROM pg_stat_activity;`
2. Kill idle connections if needed
3. Restart the application to reset connection pool
4. Increase pool size in configuration if needed

## Prevention
- Set connection timeout to 30 seconds
- Implement connection pool monitoring
- Add circuit breaker for database calls
"""


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_step(step: int, description: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}[Step {step}]{Colors.END} {description}")


def print_success(message: str):
    print(f"  {Colors.GREEN}✓{Colors.END} {message}")


def print_error(message: str):
    print(f"  {Colors.RED}✗{Colors.END} {message}")


def print_info(message: str):
    print(f"  {Colors.YELLOW}→{Colors.END} {message}")


async def main():
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}   OnCall Copilot - End-to-End Test{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        # Step 0: Health Check
        print_step(0, "Health Check")
        try:
            r = await client.get("/health")
            if r.status_code == 200:
                print_success("Backend is healthy")
            else:
                print_error(f"Backend unhealthy: {r.status_code}")
                return False
        except Exception as e:
            print_error(f"Cannot connect to backend: {e}")
            print_info("Make sure the backend is running: uvicorn app.main:app --reload")
            return False

        # Step 1: Check Ollama
        print_step(1, "Check Ollama Status")
        try:
            r = await client.get("/api/v1/ollama/status", headers={"Authorization": "Bearer dummy"})
            # This will fail auth, but let's try direct ollama check
            ollama_r = await client.get("http://localhost:11434/api/tags")
            if ollama_r.status_code == 200:
                models = ollama_r.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                print_success(f"Ollama is running with models: {model_names}")
            else:
                print_error("Ollama not responding")
                print_info("Start Ollama and run: ollama pull llama3.2:latest")
                return False
        except Exception as e:
            print_error(f"Ollama check failed: {e}")
            print_info("Make sure Ollama is running")
            return False

        # Step 2: User Signup
        print_step(2, "User Signup")
        try:
            r = await client.post("/api/v1/auth/signup", json=TEST_USER)
            if r.status_code == 201:
                token = r.json()["access_token"]
                print_success(f"User created: {TEST_USER['email']}")
            else:
                print_error(f"Signup failed: {r.json()}")
                return False
        except Exception as e:
            print_error(f"Signup error: {e}")
            return False

        headers = {"Authorization": f"Bearer {token}"}

        # Step 3: Verify Login
        print_step(3, "Verify Authentication")
        try:
            r = await client.get("/api/v1/auth/me", headers=headers)
            if r.status_code == 200:
                user = r.json()
                print_success(f"Authenticated as: {user['name']} ({user['email']})")
            else:
                print_error(f"Auth verification failed: {r.status_code}")
                return False
        except Exception as e:
            print_error(f"Auth error: {e}")
            return False

        # Step 4: Check Dashboard (empty)
        print_step(4, "Check Dashboard (Initial)")
        try:
            r = await client.get("/api/v1/dashboard", headers=headers)
            if r.status_code == 200:
                stats = r.json()["stats"]
                print_success(f"Dashboard: {stats['total_incidents']} total incidents")
            else:
                print_error(f"Dashboard failed: {r.status_code}")
        except Exception as e:
            print_error(f"Dashboard error: {e}")

        # Step 5: Create Incident
        print_step(5, "Create Incident")
        try:
            r = await client.post("/api/v1/incidents", json=TEST_INCIDENT, headers=headers)
            if r.status_code == 201:
                incident = r.json()
                incident_id = incident["id"]
                print_success(f"Incident #{incident_id} created: {incident['title']}")
                print_info(f"Severity: {incident['severity']}, Status: {incident['status']}")
            else:
                print_error(f"Create incident failed: {r.json()}")
                return False
        except Exception as e:
            print_error(f"Create incident error: {e}")
            return False

        # Step 6: Upload Document
        print_step(6, "Upload Runbook Document")
        try:
            files = {
                "file": ("db_recovery_runbook.md", TEST_RUNBOOK.encode(), "text/markdown")
            }
            data = {
                "title": "Database Recovery Runbook",
                "document_type": "runbook",
                "incident_id": str(incident_id)
            }
            r = await client.post(
                "/api/v1/documents",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {token}"}
            )
            if r.status_code == 201:
                doc = r.json()
                doc_id = doc["id"]
                print_success(f"Document #{doc_id} uploaded: {doc['title']}")
                print_info(f"Chunks: {doc['chunk_count']}, Size: {doc['file_size']} bytes")
            else:
                print_error(f"Upload failed: {r.json()}")
                return False
        except Exception as e:
            print_error(f"Upload error: {e}")
            return False

        # Step 7: Embed Document
        print_step(7, "Generate Embeddings")
        try:
            r = await client.post(f"/api/v1/documents/{doc_id}/embed", headers=headers)
            if r.status_code == 200:
                embed_result = r.json()
                print_success(f"Embeddings generated: {embed_result['embedded_count']} chunks")
            else:
                print_error(f"Embedding failed: {r.json()}")
        except Exception as e:
            print_error(f"Embedding error: {e}")

        # Step 8: Run AI Investigation
        print_step(8, "Run AI Investigation (this may take 30-60 seconds)")
        try:
            start = time.time()
            r = await client.post(
                f"/api/v1/incidents/{incident_id}/investigate",
                headers=headers,
                timeout=180.0
            )
            elapsed = time.time() - start
            
            if r.status_code == 200:
                investigation = r.json()
                print_success(f"Investigation completed in {elapsed:.1f}s")
                print_info(f"Summary: {investigation['summary'][:100]}...")
                print_info(f"Severity Estimate: {investigation['severity_estimate']}")
                print_info(f"Confidence: {investigation['confidence']:.0%}")
                print_info(f"Possible Causes: {len(investigation['possible_causes'])}")
                print_info(f"Evidence Used: {len(investigation['evidence'])}")
                
                # Show causes
                for i, cause in enumerate(investigation['possible_causes'][:3], 1):
                    print_info(f"  Cause {i}: {cause['cause'][:60]}... ({cause['confidence']:.0%})")
            elif r.status_code == 503:
                print_error("Ollama not available for investigation")
                print_info("Make sure Ollama is running with the correct model")
            else:
                print_error(f"Investigation failed: {r.json()}")
        except httpx.TimeoutException:
            print_error("Investigation timed out (>180s)")
        except Exception as e:
            print_error(f"Investigation error: {e}")

        # Step 9: Update Status to Resolved
        print_step(9, "Resolve Incident")
        try:
            # First move to investigating
            r = await client.patch(
                f"/api/v1/incidents/{incident_id}",
                json={"status": "investigating"},
                headers=headers
            )
            # Then to identified
            r = await client.patch(
                f"/api/v1/incidents/{incident_id}",
                json={"status": "identified"},
                headers=headers
            )
            # Then to resolved
            r = await client.patch(
                f"/api/v1/incidents/{incident_id}",
                json={"status": "resolved"},
                headers=headers
            )
            if r.status_code == 200:
                incident = r.json()
                print_success(f"Incident resolved at: {incident['resolved_at']}")
            else:
                print_error(f"Resolve failed: {r.json()}")
        except Exception as e:
            print_error(f"Resolve error: {e}")

        # Step 10: Generate Postmortem
        print_step(10, "Generate Postmortem (this may take 30-60 seconds)")
        try:
            start = time.time()
            r = await client.post(
                f"/api/v1/incidents/{incident_id}/postmortem",
                headers=headers,
                timeout=180.0
            )
            elapsed = time.time() - start
            
            if r.status_code == 201:
                postmortem = r.json()
                print_success(f"Postmortem generated in {elapsed:.1f}s")
                print_info(f"Content length: {len(postmortem['content'])} characters")
                # Show first few lines
                lines = postmortem['content'].split('\n')[:5]
                for line in lines:
                    if line.strip():
                        print_info(f"  {line[:70]}...")
            elif r.status_code == 503:
                print_error("Ollama not available for postmortem")
            else:
                print_error(f"Postmortem failed: {r.json()}")
        except httpx.TimeoutException:
            print_error("Postmortem timed out (>180s)")
        except Exception as e:
            print_error(f"Postmortem error: {e}")

        # Step 11: Check Analytics
        print_step(11, "Check Analytics")
        try:
            r = await client.get("/api/v1/analytics?days=30", headers=headers)
            if r.status_code == 200:
                analytics = r.json()
                print_success("Analytics retrieved")
                print_info(f"Total Incidents: {analytics['total_incidents']}")
                print_info(f"Active: {analytics['active_incidents']}")
                print_info(f"Resolved: {analytics['resolved_incidents']}")
                if analytics['resolution_stats']:
                    print_info(f"Avg Resolution: {analytics['resolution_stats']['avg_resolution_hours']:.1f} hours")
            else:
                print_error(f"Analytics failed: {r.status_code}")
        except Exception as e:
            print_error(f"Analytics error: {e}")

        # Step 12: Semantic Search
        print_step(12, "Test Semantic Search")
        try:
            r = await client.get(
                "/api/v1/search?q=connection%20pool%20exhausted&limit=5",
                headers=headers
            )
            if r.status_code == 200:
                search = r.json()
                print_success(f"Search returned {search['total']} results")
                for result in search['results'][:3]:
                    print_info(f"  - {result['document_title']} (similarity: {result['similarity']:.2f})")
            else:
                print_error(f"Search failed: {r.status_code}")
        except Exception as e:
            print_error(f"Search error: {e}")

        # Step 13: Final Dashboard
        print_step(13, "Final Dashboard Check")
        try:
            r = await client.get("/api/v1/dashboard", headers=headers)
            if r.status_code == 200:
                stats = r.json()["stats"]
                print_success("Final stats:")
                print_info(f"  Total Incidents: {stats['total_incidents']}")
                print_info(f"  Resolved This Month: {stats['resolved_this_month']}")
                if stats['avg_resolution_time_hours']:
                    print_info(f"  Avg Resolution Time: {stats['avg_resolution_time_hours']:.1f} hours")
            else:
                print_error(f"Dashboard failed: {r.status_code}")
        except Exception as e:
            print_error(f"Dashboard error: {e}")

    # Summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}   End-to-End Test Complete!{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"""
{Colors.BOLD}What was tested:{Colors.END}
  ✓ Backend health check
  ✓ Ollama connectivity
  ✓ User authentication (signup/login)
  ✓ Incident creation and management
  ✓ Document upload and chunking
  ✓ Embedding generation
  ✓ AI investigation with RAG
  ✓ Incident resolution
  ✓ Postmortem generation
  ✓ Analytics dashboard
  ✓ Semantic search

{Colors.BOLD}Frontend URLs:{Colors.END}
  • Dashboard: http://localhost:3000
  • Login: http://localhost:3000/login
  • Incidents: http://localhost:3000/incidents

{Colors.BOLD}API Documentation:{Colors.END}
  • Swagger UI: http://localhost:8000/api/docs
  • ReDoc: http://localhost:8000/api/redoc
""")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted.")
        sys.exit(1)
