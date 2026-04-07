#!/usr/bin/env python3
"""
Query HippoRAG via HTTP API.

This script provides a command-line interface to query documents
through the HippoRAG REST API with multi-tenancy support.

Usage:
    # Multi-tenancy mode (recommended)
    python query_via_api.py --query "What is X?" --business_id my_business --api_url http://localhost:8000
    python query_via_api.py --interactive --business_id my_business

    # Single-tenancy mode (backward compatible)
    python query_via_api.py --query "What is X?" --api_url http://localhost:8000
    python query_via_api.py --interactive

    # Batch queries
    python query_via_api.py --query_file queries.txt --output_file results.txt --business_id my_business
"""

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


def check_api_health(api_url: str) -> bool:
    """Check if the API server is healthy."""
    try:
        response = requests.get(f"{api_url}/health", timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False


def retrieve(
    queries: List[str],
    api_url: str = "http://localhost:8000",
    business_id: Optional[str] = None,
    num_to_retrieve: Optional[int] = None,
    return_scores: bool = False,
    use_dpr: bool = False,
    timeout: int = 300
) -> dict:
    """
    Retrieve relevant passages via the HippoRAG API.

    Args:
        queries: List of query strings
        api_url: Base URL of the HippoRAG API
        business_id: Business identifier for multi-tenancy
        num_to_retrieve: Number of documents to retrieve per query
        return_scores: Whether to return retrieval scores
        use_dpr: Use DPR retrieval instead of graph-based
        timeout: Request timeout in seconds

    Returns:
        Response data as dict
    """
    # Use business-specific endpoint if business_id is provided
    if business_id:
        endpoint = "/business/retrieve"
    else:
        endpoint = "/retrieve/dpr" if use_dpr else "/retrieve"

    payload = {
        "queries": queries,
        "return_scores": return_scores
    }
    if num_to_retrieve is not None:
        payload["num_to_retrieve"] = num_to_retrieve
    if business_id:
        payload["business_id"] = business_id

    response = requests.post(
        f"{api_url}{endpoint}",
        json=payload,
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()


def question_answering(
    queries: List[str],
    api_url: str = "http://localhost:8000",
    business_id: Optional[str] = None,
    num_to_retrieve: Optional[int] = None,
    use_dpr: bool = False,
    timeout: int = 300
) -> dict:
    """
    Answer questions via the HippoRAG API.

    Args:
        queries: List of question strings
        api_url: Base URL of the HippoRAG API
        business_id: Business identifier for multi-tenancy
        num_to_retrieve: Number of documents to retrieve per query
        use_dpr: Use DPR QA instead of graph-based
        timeout: Request timeout in seconds

    Returns:
        Response data as dict
    """
    # Use business-specific endpoint if business_id is provided
    if business_id:
        endpoint = "/business/qa"
    else:
        endpoint = "/qa/dpr" if use_dpr else "/qa"

    payload = {"queries": queries}
    if num_to_retrieve is not None:
        payload["num_to_retrieve"] = num_to_retrieve
    if business_id:
        payload["business_id"] = business_id

    response = requests.post(
        f"{api_url}{endpoint}",
        json=payload,
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()


def bind_books_to_business(api_url: str, business_id: str, book_ids: List[str]) -> dict:
    """Bind books to a business."""
    response = requests.post(
        f"{api_url}/business/bind",
        json={"business_id": business_id, "book_ids": book_ids},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def unbind_books_from_business(api_url: str, business_id: str, book_ids: List[str]) -> dict:
    """Unbind books from a business."""
    response = requests.post(
        f"{api_url}/business/unbind",
        json={"business_id": business_id, "book_ids": book_ids},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_business_books(api_url: str, business_id: str) -> dict:
    """Get books bound to a business."""
    response = requests.get(
        f"{api_url}/business/books",
        params={"business_id": business_id},
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def print_qa_result(result: dict, show_passages: bool = True, max_passage_len: int = 200):
    """Pretty print a QA result."""
    print("\n" + "=" * 60)
    print(f"Query: {result['query']}")
    print("=" * 60)
    print(f"\nAnswer: {result['answer']}")

    if show_passages and result.get('passages'):
        print("\n" + "-" * 60)
        print("Retrieved passages:")
        print("-" * 60)
        for i, passage in enumerate(result['passages'][:3], 1):
            content = passage['content']
            if len(content) > max_passage_len:
                content = content[:max_passage_len] + "..."
            doc_id = passage.get('doc_id')
            doc_info = f" (doc_id: {doc_id})" if doc_id else ""
            print(f"\n[{i}]{doc_info}")
            print(content)


def print_retrieve_result(result: dict, max_passage_len: int = 200):
    """Pretty print a retrieve result."""
    print("\n" + "=" * 60)
    print(f"Query: {result['query']}")
    print("=" * 60)

    if result.get('passages'):
        print(f"\nRetrieved {len(result['passages'])} passages:")
        for i, passage in enumerate(result['passages'], 1):
            content = passage['content']
            if len(content) > max_passage_len:
                content = content[:max_passage_len] + "..."
            doc_id = passage.get('doc_id')
            score = result['scores'][i - 1] if result.get('scores') else None

            doc_info = f" (doc_id: {doc_id})" if doc_id else ""
            score_info = f" [score: {score:.4f}]" if score else ""
            print(f"\n[{i}]{doc_info}{score_info}")
            print(content)


def interactive_qa(api_url: str, business_id: Optional[str] = None,
                   use_dpr: bool = False, num_to_retrieve: Optional[int] = None):
    """Interactive QA mode."""
    print("\n" + "=" * 60)
    print("HippoRAG Query Interface")
    print("=" * 60)
    print(f"\nAPI URL: {api_url}")
    if business_id:
        print(f"Business ID: {business_id}")
    print(f"Mode: {'DPR' if use_dpr else 'Graph-based'}")
    print("\nType 'exit' or 'quit' to end.")
    print("Type 'switch' to toggle between graph-based and DPR mode.\n")

    current_dpr = use_dpr

    while True:
        try:
            query = input("\nEnter your query: ").strip()

            if query.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break

            if query.lower() == 'switch':
                current_dpr = not current_dpr
                print(f"Switched to {'DPR' if current_dpr else 'Graph-based'} mode")
                continue

            if not query:
                continue

            print("\nProcessing query...")
            result = question_answering(
                queries=[query],
                api_url=api_url,
                business_id=business_id,
                num_to_retrieve=num_to_retrieve,
                use_dpr=current_dpr
            )

            if result.get('results'):
                print_qa_result(result['results'][0])
            else:
                print("No answer found.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")


def batch_query(
    queries: List[str],
    api_url: str,
    business_id: Optional[str] = None,
    output_file: Optional[str] = None,
    use_dpr: bool = False,
    num_to_retrieve: Optional[int] = None,
    mode: str = "qa"
):
    """Process multiple queries at once."""
    print(f"\nProcessing {len(queries)} queries...")

    if mode == "qa":
        result = question_answering(
            queries=queries,
            api_url=api_url,
            business_id=business_id,
            num_to_retrieve=num_to_retrieve,
            use_dpr=use_dpr
        )
    else:
        result = retrieve(
            queries=queries,
            api_url=api_url,
            business_id=business_id,
            num_to_retrieve=num_to_retrieve,
            use_dpr=use_dpr
        )

    output_lines = []
    results_key = 'results'

    for i, query_result in enumerate(result.get(results_key, []), 1):
        if mode == "qa":
            output_lines.append(f"\n{'=' * 60}")
            output_lines.append(f"Query {i}: {query_result['query']}")
            output_lines.append(f"{'=' * 60}")
            output_lines.append(f"Answer: {query_result['answer']}")
            output_lines.append("")

            print(f"\nQuery {i}: {query_result['query']}")
            print(f"Answer: {query_result['answer']}")
        else:
            output_lines.append(f"\n{'=' * 60}")
            output_lines.append(f"Query {i}: {query_result['query']}")
            output_lines.append(f"{'=' * 60}")
            output_lines.append(f"Retrieved: {len(query_result['passages'])} passages")

            print(f"\nQuery {i}: {query_result['query']}")
            print(f"Retrieved: {len(query_result['passages'])} passages")

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\nResults saved to: {output_file}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Query HippoRAG via HTTP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Multi-tenancy mode
    python query_via_api.py --query "What is X?" --business_id my_business

    # Interactive mode
    python query_via_api.py --interactive --business_id my_business

    # Manage business bindings
    python query_via_api.py --business_id my_business --bind_books book1 book2
    python query_via_api.py --business_id my_business --show_books
        """
    )
    parser.add_argument(
        '--api_url',
        type=str,
        default='http://localhost:8000',
        help='HippoRAG API base URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--business_id',
        type=str,
        default=None,
        help='Business identifier for multi-tenancy (optional)'
    )
    parser.add_argument(
        '--query',
        type=str,
        default=None,
        help='Single query to execute'
    )
    parser.add_argument(
        '--query_file',
        type=str,
        default=None,
        help='File containing queries (one per line)'
    )
    parser.add_argument(
        '--output_file',
        type=str,
        default=None,
        help='Output file for batch query results'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )
    parser.add_argument(
        '--dpr',
        action='store_true',
        help='Use DPR retrieval instead of graph-based'
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['qa', 'retrieve'],
        default='qa',
        help='Query mode: qa (question answering) or retrieve (passage retrieval)'
    )
    parser.add_argument(
        '--num_to_retrieve',
        type=int,
        default=None,
        help='Number of documents to retrieve per query'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Request timeout in seconds (default: 300)'
    )

    # Business management arguments
    parser.add_argument(
        '--bind_books',
        nargs='+',
        type=str,
        default=None,
        help='Bind books to business (requires --business_id)'
    )
    parser.add_argument(
        '--unbind_books',
        nargs='+',
        type=str,
        default=None,
        help='Unbind books from business (requires --business_id)'
    )
    parser.add_argument(
        '--show_books',
        action='store_true',
        help='Show books bound to business (requires --business_id)'
    )

    args = parser.parse_args()

    # Check API health
    if not check_api_health(args.api_url):
        logger.error(f"API server is not available at {args.api_url}")
        logger.error("Make sure the server is running: uvicorn hipporag.api:app --host 0.0.0.0 --port 8000")
        return 1

    # Business management mode
    if args.bind_books:
        if not args.business_id:
            logger.error("--business_id is required when using --bind_books")
            return 1
        logger.info(f"Binding books to business '{args.business_id}': {args.bind_books}")
        result = bind_books_to_business(args.api_url, args.business_id, args.bind_books)
        print(f"\nStatus: {result['status']}")
        print(f"Bound books: {result.get('book_ids', [])}")
        return 0

    if args.unbind_books:
        if not args.business_id:
            logger.error("--business_id is required when using --unbind_books")
            return 1
        logger.info(f"Unbinding books from business '{args.business_id}': {args.unbind_books}")
        result = unbind_books_from_business(args.api_url, args.business_id, args.unbind_books)
        print(f"\nStatus: {result['status']}")
        return 0

    if args.show_books:
        if not args.business_id:
            logger.error("--business_id is required when using --show_books")
            return 1
        result = get_business_books(args.api_url, args.business_id)
        print(f"\nBooks bound to business '{args.business_id}':")
        for book in result.get('books', []):
            print(f"  - {book['book_id']}: {book.get('doc_count', 0)} docs")
        return 0

    # Interactive mode
    if args.interactive:
        interactive_qa(
            api_url=args.api_url,
            business_id=args.business_id,
            use_dpr=args.dpr,
            num_to_retrieve=args.num_to_retrieve
        )
        return 0

    # Batch query mode
    queries = []
    if args.query_file:
        with open(args.query_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]
    elif args.query:
        queries = [args.query]
    else:
        # Default to interactive mode
        interactive_qa(
            api_url=args.api_url,
            business_id=args.business_id,
            use_dpr=args.dpr,
            num_to_retrieve=args.num_to_retrieve
        )
        return 0

    if not queries:
        logger.error("No queries to process")
        return 1

    try:
        batch_query(
            queries=queries,
            api_url=args.api_url,
            business_id=args.business_id,
            output_file=args.output_file,
            use_dpr=args.dpr,
            num_to_retrieve=args.num_to_retrieve,
            mode=args.mode
        )
        return 0

    except Exception as e:
        logger.error(f"Failed to process queries: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
