#!/usr/bin/env python3
"""
Example: Using MultiTenancyManager to manage multiple books and businesses

This example demonstrates the new multi-tenancy approach:
1. Create a MultiTenancyManager with database backend
2. Add multiple books (each book has isolated data)
3. Create businesses and bind books to them
4. Query through business interface (searches across bound books)
5. Manage book and business metadata

Comparison with old approach:
- Old (MultiBookHippoRAG): In-memory, single process, no persistence
- New (MultiTenancyManager): Database-backed, persistent, supports business_id
"""

import os
import json
import logging
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from hipporag.multi_tenancy import MultiTenancyManager
from hipporag.utils.config_utils import BaseConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_chapters_from_file(filepath: str) -> List[str]:
    """Load chapters from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
        if isinstance(chapters, list):
            return [str(ch) for ch in chapters if ch]
        else:
            raise ValueError("JSON file must contain an array of chapter strings")


def get_env_config():
    """Get configuration from environment variables."""
    llm_model = os.getenv('HIPPORAG_LLM_MODEL') or os.getenv('LLM_NAME', 'gpt-4o-mini')
    embedding_model = os.getenv('HIPPORAG_EMBEDDING_MODEL') or os.getenv('EMBEDDING_NAME', 'text-embedding-3-small')
    base_url = os.getenv('OPENAI_BASE_URL') or os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    llm_base_url = os.getenv('HIPPORAG_LLM_BASE_URL') or os.getenv('LLM_BASE_URL') or base_url
    embedding_base_url = os.getenv('HIPPORAG_EMBEDDING_BASE_URL') or os.getenv('EMBEDDING_BASE_URL') or base_url

    return {
        'llm_model': llm_model,
        'embedding_model': embedding_model,
        'llm_base_url': llm_base_url,
        'embedding_base_url': embedding_base_url,
    }


def main():
    """Main example function."""

    # 1. Create base configuration
    env_config = get_env_config()

    config = BaseConfig(
        save_dir=os.getenv('HIPPORAG_SAVE_DIR', './outputs'),
        llm_name=env_config['llm_model'],
        embedding_model_name=env_config['embedding_model'],
        llm_base_url=env_config['llm_base_url'],
        embedding_base_url=env_config['embedding_base_url'],
        retrieval_top_k=200,
        linking_top_k=5,
        max_qa_steps=3,
        qa_top_k=5,
        graph_type="facts_and_sim_passage_node_unidirectional",
        embedding_batch_size=8,
        openie_mode="online",
        save_openie=True,
        # Graph library: use dgraph
        graph_library="dgraph",
        dgraph_config={
            "host": os.getenv('DGRAPH_GRPC', 'localhost:9080').split(':')[0],
            "port": int(os.getenv('DGRAPH_GRPC', 'localhost:9080').split(':')[1]) if ':' in os.getenv('DGRAPH_GRPC', 'localhost:9080') else 9080
        },
        # pgvector configuration
        use_pgvector=True,
        pgvector_host=os.getenv('PGVECTOR_HOST', 'localhost'),
        pgvector_port=int(os.getenv('PGVECTOR_PORT', '5432')),
        pgvector_database=os.getenv('PGVECTOR_DATABASE', 'hipporag'),
        pgvector_user=os.getenv('PGVECTOR_USER', 'postgres'),
        pgvector_password=os.getenv('PGVECTOR_PASSWORD', ''),
    )

    # 2. Create MultiTenancyManager
    print("\n" + "=" * 60)
    print("Creating MultiTenancyManager")
    print("=" * 60)

    manager = MultiTenancyManager(base_config=config)

    # 3. Add books (each book has isolated data)
    print("\n" + "=" * 60)
    print("Adding Books")
    print("=" * 60)

    # Book 1: Alice in Wonderland
    book1_chapters = [
        "Alice was beginning to get very tired of sitting by her sister on the bank.",
        "The White Rabbit put on his spectacles. 'Where shall I begin, please your Majesty?'",
        "The Queen turned crimson with fury, and, after glaring at her for a moment like a wild beast, screamed 'Off with her head!'"
    ]

    manager.add_book(
        book_id="alice_in_wonderland",
        docs=book1_chapters,
        metadata={
            'title': 'Alice in Wonderland',
            'author': 'Lewis Carroll',
            'year': 1865
        }
    )
    print("Added book: alice_in_wonderland")

    # Book 2: Literary Quotes
    book2_chapters = [
        "It was the best of times, it was the worst of times.",
        "A wonderful fact to reflect upon, that every human creature is constituted to be that profound secret and mystery to every other.",
        "I have a dream that one day this nation will rise up and live out the true meaning of its creed."
    ]

    manager.add_book(
        book_id="literary_quotes",
        docs=book2_chapters,
        metadata={
            'title': 'Literary Quotes Collection',
            'author': 'Various',
            'description': 'A collection of famous literary quotes'
        }
    )
    print("Added book: literary_quotes")

    # Book 3: Technical Documentation
    book3_chapters = [
        "The system architecture consists of three main components: the frontend, backend, and database.",
        "API endpoints are documented using OpenAPI specification version 3.0.",
        "Authentication is handled via JWT tokens with a 24-hour expiration time."
    ]

    manager.add_book(
        book_id="tech_docs",
        docs=book3_chapters,
        metadata={
            'title': 'Technical Documentation',
            'category': 'documentation'
        }
    )
    print("Added book: tech_docs")

    # 4. List all books
    print("\n" + "=" * 60)
    print("All Books")
    print("=" * 60)
    books = manager.list_books()
    for book in books:
        print(f"  - {book['book_id']}: {book.get('doc_count', 0)} docs, status: {book.get('status', 'unknown')}")

    # 5. Create businesses and bind books
    print("\n" + "=" * 60)
    print("Creating Businesses and Binding Books")
    print("=" * 60)

    # Business A: Literature Research (can access book 1 and 2)
    manager.bind_books_to_business(
        business_id="literature_research",
        book_ids=["alice_in_wonderland", "literary_quotes"]
    )
    print("Created business 'literature_research' with books: alice_in_wonderland, literary_quotes")

    # Business B: Technical Team (can access book 2 and 3)
    manager.bind_books_to_business(
        business_id="tech_team",
        book_ids=["literary_quotes", "tech_docs"]
    )
    print("Created business 'tech_team' with books: literary_quotes, tech_docs")

    # 6. List businesses
    print("\n" + "=" * 60)
    print("Businesses and Their Books")
    print("=" * 60)
    businesses = manager.list_businesses()
    for business in businesses:
        print(f"\n  Business: {business['business_id']}")
        books = manager.get_business_books(business['business_id'])
        for book in books:
            print(f"    - {book['book_id']}")

    # 7. Query through business interface
    print("\n" + "=" * 60)
    print("Querying Through Business Interface")
    print("=" * 60)

    # Query from literature_research perspective
    query = "What happened to Alice?"
    print(f"\nQuery (literature_research): {query}")
    solutions, answers, metadata = manager.query_business(
        business_id="literature_research",
        queries=[query]
    )
    if solutions and len(solutions) > 0:
        print(f"Answer: {answers[0] if answers else 'No answer'}")

    # Query from tech_team perspective (should NOT find Alice)
    print(f"\nQuery (tech_team): {query}")
    solutions, answers, metadata = manager.query_business(
        business_id="tech_team",
        queries=[query]
    )
    if solutions and len(solutions) > 0:
        print(f"Answer: {answers[0] if answers else 'No answer'}")
        print("(tech_team doesn't have access to alice_in_wonderland)")

    # Query about technical content
    query = "What is the system architecture?"
    print(f"\nQuery (tech_team): {query}")
    solutions, answers, metadata = manager.query_business(
        business_id="tech_team",
        queries=[query]
    )
    if solutions and len(solutions) > 0:
        print(f"Answer: {answers[0] if answers else 'No answer'}")

    # 8. Retrieve passages through business interface
    print("\n" + "=" * 60)
    print("Retrieving Passages")
    print("=" * 60)

    query = "time"
    print(f"\nRetrieve (literature_research): {query}")
    solutions, metadata = manager.retrieve_business(
        business_id="literature_research",
        queries=[query],
        num_to_retrieve=3
    )
    if solutions and len(solutions) > 0:
        print(f"Found {len(solutions[0].docs) if hasattr(solutions[0], 'docs') else 0} passages")

    # 9. Unbind a book from business
    print("\n" + "=" * 60)
    print("Unbinding Books")
    print("=" * 60)

    manager.unbind_books_from_business(
        business_id="literature_research",
        book_ids=["literary_quotes"]
    )
    print("Unbound 'literary_quotes' from 'literature_research'")

    books = manager.get_business_books("literature_research")
    print("\nBooks now bound to 'literature_research':")
    for book in books:
        print(f"  - {book['book_id']}")

    # 10. Delete a book
    print("\n" + "=" * 60)
    print("Deleting a Book")
    print("=" * 60)

    manager.delete_book("tech_docs")
    print("Deleted book: tech_docs")

    books = manager.list_books()
    print(f"\nRemaining books: {[b['book_id'] for b in books]}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)
    print("\nKey concepts:")
    print("  - book_id: Isolates data for each book (embeddings, graph nodes)")
    print("  - business_id: Access control layer (many-to-many with books)")
    print("  - Business queries only search across bound books")
    print("  - Deleting a book removes its data from all stores")


if __name__ == "__main__":
    main()
