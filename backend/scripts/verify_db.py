#!/usr/bin/env python3
"""Verify database connection and pgvector extension for CI."""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def verify_database() -> bool:
    """Verify database connection and pgvector extension."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return False

    print(f"Connecting to: {database_url.split('@')[1] if '@' in database_url else database_url}")

    try:
        engine = create_async_engine(database_url)
        async with engine.begin() as conn:
            # Check connection
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"PostgreSQL: {version}")

            # Create pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            print("pgvector extension created/verified")

            # Verify extension
            result = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            if row:
                print(f"pgvector version: {row[1]}")
            else:
                print("ERROR: pgvector extension not found!")
                return False

        await engine.dispose()
        print("Database verification successful!")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(verify_database())
    sys.exit(0 if success else 1)
