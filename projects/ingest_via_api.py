#!/usr/bin/env python3
"""
Ingest documents into HippoRAG via HTTP API.

This script provides a command-line interface to index documents
through the HippoRAG REST API with multi-tenancy support.

Usage:
    # Single-tenancy mode (backward compatible)
    python ingest_via_api.py --chapters_file chapters.json --api_url http://localhost:8000

    # Multi-tenancy mode (recommended)
    python ingest_via_api.py --chapters_file chapters.json --book_id my_book_001 --api_url http://localhost:8000

    # Direct document input
    python ingest_via_api.py --docs "Doc 1" "Doc 2" --book_id my_book_001
"""

import os
import json
import argparse
import logging
from typing import List, Optional

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_docs_from_file(filepath: str) -> List[str]:
    """
    Load documents from a JSON file.
    Expected format: JSON array of strings, e.g., ["doc1 text...", "doc2 text..."]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        docs = json.load(f)
        if isinstance(docs, list):
            return [str(doc) for doc in docs if doc]
        else:
            raise ValueError("JSON file must contain an array of document strings")


def check_api_health(api_url: str) -> bool:
    """Check if the API server is healthy."""
    try:
        response = requests.get(f"{api_url}/health", timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_indexing_status(api_url: str) -> dict:
    """Get the current indexing status from the API."""
    try:
        response = requests.get(f"{api_url}/status", timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"status": "unknown", "message": "Failed to get status"}
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}


def ingest_documents(
    docs: List[str],
    api_url: str = "http://localhost:8000",
    book_id: Optional[str] = None,
    sync: bool = True,
    timeout: int = 3600
) -> dict:
    """
    Ingest documents via the HippoRAG API.

    Args:
        docs: List of document strings to index
        api_url: Base URL of the HippoRAG API
        book_id: Book identifier for multi-tenancy (optional)
        sync: If True, use synchronous indexing (wait for completion)
        timeout: Request timeout in seconds (for sync mode)

    Returns:
        Response data as dict
    """
    # Use book-specific endpoint if book_id is provided
    if book_id:
        endpoint = "/book/index/sync" if sync else "/book/index"
    else:
        endpoint = "/index/sync" if sync else "/index"

    logger.info(f"Indexing {len(docs)} documents via API: {api_url}{endpoint}")
    logger.info(f"Total characters: {sum(len(doc) for doc in docs)}")
    if book_id:
        logger.info(f"Book ID: {book_id}")

    payload = {"docs": docs}
    if book_id:
        payload["book_id"] = book_id

    try:
        response = requests.post(
            f"{api_url}{endpoint}",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to index documents: {e}")
        raise


def list_books(api_url: str) -> dict:
    """List all books from the API."""
    response = requests.get(f"{api_url}/books", timeout=30)
    response.raise_for_status()
    return response.json()


def delete_book(api_url: str, book_id: str) -> dict:
    """Delete a book from the API."""
    response = requests.delete(f"{api_url}/book?book_id={book_id}", timeout=60)
    response.raise_for_status()
    return response.json()


def wait_for_indexing_complete(api_url: str, poll_interval: int = 5, timeout: int = 3600) -> bool:
    """
    Wait for asynchronous indexing to complete.

    Args:
        api_url: Base URL of the HippoRAG API
        poll_interval: Seconds between status checks
        timeout: Maximum wait time in seconds

    Returns:
        True if indexing completed successfully, False otherwise
    """
    import time
    start_time = time.time()

    while time.time() - start_time < timeout:
        status = get_indexing_status(api_url)

        if status["status"] == "completed":
            logger.info("Indexing completed successfully!")
            return True
        elif status["status"] == "failed":
            logger.error(f"Indexing failed: {status.get('message', 'Unknown error')}")
            return False
        elif status["status"] == "indexing":
            logger.info(f"Indexing in progress... {status.get('message', '')}")
        else:
            logger.info(f"Status: {status['status']} - {status.get('message', '')}")

        time.sleep(poll_interval)

    logger.error("Indexing timed out")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into HippoRAG via HTTP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Multi-tenancy mode (recommended)
    python ingest_via_api.py --chapters_file chapters.json --book_id my_book_001

    # Single-tenancy mode (backward compatible)
    python ingest_via_api.py --chapters_file chapters.json

    # List all books
    python ingest_via_api.py --list_books

    # Delete a book
    python ingest_via_api.py --delete_book my_book_001
        """
    )
    parser.add_argument(
        '--api_url',
        type=str,
        default='http://localhost:8000',
        help='HippoRAG API base URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--chapters_file',
        type=str,
        default=None,
        help='Path to JSON file containing list of document strings. '
             'Format: ["doc1 text...", "doc2 text..."]'
    )
    parser.add_argument(
        '--docs',
        nargs='+',
        type=str,
        default=None,
        help='Documents to index (space-separated strings)'
    )
    parser.add_argument(
        '--book_id',
        type=str,
        default=None,
        help='Book identifier for multi-tenancy (optional, recommended)'
    )
    parser.add_argument(
        '--async',
        dest='async_mode',
        action='store_true',
        help='Use asynchronous indexing (returns immediately, check status separately)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=3600,
        help='Request timeout in seconds (default: 3600)'
    )
    parser.add_argument(
        '--check_status',
        action='store_true',
        help='Only check indexing status, do not index'
    )
    parser.add_argument(
        '--list_books',
        action='store_true',
        help='List all books'
    )
    parser.add_argument(
        '--delete_book',
        type=str,
        default=None,
        help='Delete a book by book_id'
    )

    args = parser.parse_args()

    # Check API health
    if not check_api_health(args.api_url):
        logger.error(f"API server is not available at {args.api_url}")
        logger.error("Make sure the server is running: uvicorn hipporag.api:app --host 0.0.0.0 --port 8000")
        return 1

    # List books mode
    if args.list_books:
        result = list_books(args.api_url)
        print("\n" + "=" * 60)
        print("Books:")
        print("=" * 60)
        for book in result.get('books', []):
            print(f"  - {book['book_id']}: {book.get('doc_count', 0)} docs, status: {book.get('status', 'unknown')}")
        return 0

    # Delete book mode
    if args.delete_book:
        logger.info(f"Deleting book: {args.delete_book}")
        result = delete_book(args.api_url, args.delete_book)
        print(f"\nStatus: {result['status']}")
        print(f"Message: {result.get('message', 'N/A')}")
        return 0

    # Check status only
    if args.check_status:
        status = get_indexing_status(args.api_url)
        print(f"Indexing status: {status['status']}")
        print(f"Message: {status['message']}")
        return 0

    # Load documents
    if args.chapters_file:
        logger.info(f"Loading documents from: {args.chapters_file}")
        docs = load_docs_from_file(args.chapters_file)
    elif args.docs:
        docs = args.docs
    else:
        logger.error("Please provide documents via --chapters_file or --docs")
        return 1

    if not docs:
        logger.error("No documents to index")
        return 1

    # Index documents
    try:
        result = ingest_documents(
            docs=docs,
            api_url=args.api_url,
            book_id=args.book_id,
            sync=not args.async_mode,
            timeout=args.timeout
        )

        print(f"\nStatus: {result['status']}")
        print(f"Message: {result.get('message', 'N/A')}")
        print(f"Documents indexed: {result['num_docs']}")
        if args.book_id:
            print(f"Book ID: {result.get('book_id', args.book_id)}")

        # If async mode, wait for completion
        if args.async_mode:
            logger.info("Waiting for indexing to complete...")
            if wait_for_indexing_complete(args.api_url, timeout=args.timeout):
                return 0
            return 1

        return 0

    except Exception as e:
        logger.error(f"Failed to ingest documents: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
