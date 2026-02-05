#!/usr/bin/env python3
"""
Example: Using MultiBookHippoRAG to manage multiple books

This example demonstrates how to:
1. Create a MultiBookHippoRAG manager
2. Add multiple books
3. Query individual books
4. Query across multiple books
5. Manage book metadata
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

from hipporag import MultiBookHippoRAG
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


def main():
    """Main example function."""
    
    # 1. Create base configuration
    config = BaseConfig(
        save_dir='outputs/multi_books',
        llm_name=os.getenv('LLM_NAME', 'gpt-4o-mini'),
        embedding_model_name=os.getenv('EMBEDDING_NAME', 'text-embedding-3-small'),
        llm_base_url=os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'),
        embedding_base_url=os.getenv('EMBEDDING_BASE_URL') or os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'),
        retrieval_top_k=200,
        linking_top_k=5,
        max_qa_steps=3,
        qa_top_k=5,
        graph_type="facts_and_sim_passage_node_unidirectional",
        embedding_batch_size=8,
        openie_mode="online",
        save_openie=True,
        # Optional: Enable pgvector or Nebula Graph
        # use_pgvector=True,
        # pgvector_host='localhost',
        # pgvector_port=5432,
        # pgvector_database='hipporag',
        # pgvector_user='postgres',
        # pgvector_password='your_password',
        # use_nebula_graph=True,
        # nebula_host='127.0.0.1',
        # nebula_port=9669,
        # nebula_user='root',
        # nebula_password='nebula',
        # nebula_space_name='hipporag',
    )
    
    # 2. Create MultiBookHippoRAG manager
    manager = MultiBookHippoRAG(base_config=config)
    
    # 3. Add books
    # Example: Add book 1
    book1_chapters = [
        "Alice was beginning to get very tired of sitting by her sister on the bank.",
        "The White Rabbit put on his spectacles. 'Where shall I begin, please your Majesty?'",
        "The Queen turned crimson with fury, and, after glaring at her for a moment like a wild beast, screamed 'Off with her head!'"
    ]
    
    manager.add_book(
        book_id="alice_in_wonderland",
        chapters=book1_chapters,
        metadata={
            'title': 'Alice in Wonderland',
            'author': 'Lewis Carroll',
            'year': 1865
        }
    )
    
    # Example: Add book 2
    book2_chapters = [
        "It was the best of times, it was the worst of times.",
        "A wonderful fact to reflect upon, that every human creature is constituted to be that profound secret and mystery to every other.",
        "I have a dream that one day this nation will rise up and live out the true meaning of its creed."
    ]
    
    manager.add_book(
        book_id="literary_quotes",
        chapters=book2_chapters,
        metadata={
            'title': 'Literary Quotes Collection',
            'author': 'Various',
            'description': 'A collection of famous literary quotes'
        }
    )
    
    # 4. List all books
    print("\n" + "="*60)
    print("All Books:")
    print("="*60)
    books = manager.list_books()
    for book in books:
        print(f"  - {book['book_id']}: {book.get('title', 'N/A')} ({book.get('num_chapters', 0)} chapters)")
    
    # 5. Get book information
    print("\n" + "="*60)
    print("Book Information:")
    print("="*60)
    book_info = manager.get_book_info("alice_in_wonderland")
    print(json.dumps(book_info, indent=2, default=str))
    
    # 6. Query single book
    print("\n" + "="*60)
    print("Query Single Book:")
    print("="*60)
    query = "What happened to Alice?"
    solutions, messages, metadata = manager.query_single_book("alice_in_wonderland", query)
    
    if solutions:
        solution = solutions[0]
        print(f"Query: {query}")
        print(f"Answer: {solution.answer}")
        print(f"\nRetrieved Documents:")
        for i, doc in enumerate(solution.docs[:3], 1):
            print(f"  [{i}] {doc[:100]}...")
    
    # 7. Query multiple books
    print("\n" + "="*60)
    print("Query Multiple Books:")
    print("="*60)
    query = "What is the main theme?"
    results = manager.query(
        query=query,
        book_ids=["alice_in_wonderland", "literary_quotes"],
        merge_results=True
    )
    
    print(f"Query: {query}")
    print(f"\nFound {len(results)} results across books:")
    for i, solution in enumerate(results[:3], 1):
        book_id = solution.metadata.get('book_id', 'unknown')
        print(f"\n  [{i}] From book '{book_id}':")
        print(f"      Answer: {solution.answer[:100]}...")
        print(f"      Top doc: {solution.docs[0][:80]}..." if solution.docs else "      No docs")
    
    # 8. Query without merging (get results per book)
    print("\n" + "="*60)
    print("Query Without Merging (Per Book):")
    print("="*60)
    query = "What is the main character?"
    book_results = manager.query(
        query=query,
        book_ids=["alice_in_wonderland", "literary_quotes"],
        merge_results=False
    )
    
    print(f"Query: {query}")
    for book_id, (solutions, messages, metadata) in book_results.items():
        print(f"\n  Book '{book_id}':")
        if solutions:
            solution = solutions[0]
            print(f"    Answer: {solution.answer[:100]}...")
        else:
            print("    No results")
    
    # 9. Load existing book (if you restart the script)
    print("\n" + "="*60)
    print("Loading Existing Book:")
    print("="*60)
    try:
        # This will load the book if it was previously indexed
        existing_book = manager.load_existing_book("alice_in_wonderland")
        print("Successfully loaded existing book")
    except ValueError as e:
        print(f"Could not load: {e}")
    
    print("\n" + "="*60)
    print("Example completed!")
    print("="*60)


if __name__ == "__main__":
    main()

