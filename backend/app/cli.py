"""CLI commands for OnCall Copilot."""

import argparse
import asyncio
import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI commands."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def run_embedding_worker_cmd(poll_interval: float) -> None:
    """Run the embedding worker."""
    from app.workers.embedding_worker import run_embedding_worker

    await run_embedding_worker(poll_interval=poll_interval)


async def process_embeddings_cmd(max_batches: int | None) -> None:
    """Process pending embeddings once."""
    from app.workers.embedding_worker import process_embedding_queue

    total = await process_embedding_queue(max_iterations=max_batches)
    print(f"Processed {total} chunks")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OnCall Copilot CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # embedding-worker command
    worker_parser = subparsers.add_parser(
        "embedding-worker",
        help="Run the background embedding worker",
        description="Continuously process pending document chunks for embedding generation.",
    )
    worker_parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between polling for new chunks (default: 5.0)",
    )

    # process-embeddings command
    process_parser = subparsers.add_parser(
        "process-embeddings",
        help="Process pending embeddings once and exit",
        description="Process pending document chunks for embedding generation, then exit.",
    )
    process_parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum number of batches to process (default: unlimited)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)

    if args.command == "embedding-worker":
        print("Starting embedding worker (Ctrl+C to stop)...")
        try:
            asyncio.run(run_embedding_worker_cmd(args.poll_interval))
        except KeyboardInterrupt:
            print("\nEmbedding worker stopped.")

    elif args.command == "process-embeddings":
        asyncio.run(process_embeddings_cmd(args.max_batches))


if __name__ == "__main__":
    main()
