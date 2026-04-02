"""
API routes for HippoRAG.

Defines all RESTful endpoints for indexing, retrieval, and QA operations.
"""

import asyncio
import json
import logging
from typing import List, AsyncGenerator

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from .models import (
    IndexRequest, IndexResponse,
    RetrieveRequest, RetrieveResponse, QueryResult, Passage,
    QARequest, QAResponse, QAResult,
    DPRRequest, DPRQARequest,
    HealthResponse, StatusResponse,
    BookIndexRequest, BookIndexResponse, BookInfo, BooksListResponse,
    BusinessBindRequest, BusinessBindResponse, BusinessUnbindRequest,
    BusinessBooksResponse, BusinessQARequest, BusinessQAResponse, BusinessQAResult,
    BusinessRetrieveRequest, BusinessRetrieveResponse, BusinessPassage,
    BusinessQueryResult, BookDeleteResponse,
    # Book management models
    BookCreateRequest, BookCreateResponse,
    # Business management models
    BusinessCreateRequest, BusinessCreateResponse, BusinessInfo, BusinessUpdateRequest,
    BusinessUpdateResponse, BusinessesListResponse, BusinessDeleteResponse
)
from .dependencies import (
    get_hipporag, get_indexing_status, set_indexing_status, is_hipporag_initialized,
    get_multi_tenancy_manager, get_indexing_progress, set_indexing_progress, reset_indexing_progress
)

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_upload_bytes_to_docs(content: bytes, filename: str) -> List[str]:
    """
    Parse uploaded file bytes into document strings (same rules as POST /index/upload).

    Raises UnicodeDecodeError, json.JSONDecodeError, or ValueError on invalid input.
    """
    fn = (filename or "unknown.txt").lower()
    docs: List[str] = []

    if fn.endswith(".json"):
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    docs.append(item)
                elif isinstance(item, dict) and "content" in item:
                    docs.append(item["content"])
        elif isinstance(data, dict) and "content" in data:
            docs.append(data["content"])
        else:
            raise ValueError("JSON must be array of strings or objects with 'content' field")

    elif fn.endswith(".jsonl"):
        for line in content.decode("utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    if isinstance(item, str):
                        docs.append(item)
                    elif isinstance(item, dict) and "content" in item:
                        docs.append(item["content"])
                except json.JSONDecodeError:
                    docs.append(line)

    else:
        text = content.decode("utf-8")
        paragraphs = text.split("\n\n")
        if len(paragraphs) == 1:
            paragraphs = text.split("\n")
        for p in paragraphs:
            p = p.strip()
            if p:
                docs.append(p)

    return docs


# ============== Health and Status Endpoints ==============

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    status = get_indexing_status()
    return HealthResponse(
        status="healthy",
        hipporag_initialized=is_hipporag_initialized(),
        indexing_status=status["status"]
    )


@router.get("/status", response_model=StatusResponse, tags=["Status"])
async def get_status():
    """Get current indexing status."""
    status = get_indexing_status()
    return StatusResponse(
        indexing_status=status["status"],
        message=status["message"]
    )


# ============== SSE Progress Endpoint ==============

@router.get("/index/progress", tags=["Indexing"])
async def index_progress_stream():
    """
    SSE endpoint for real-time indexing progress.

    Returns Server-Sent Events with progress updates during indexing.
    Use this to track progress of large file indexing operations.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        last_progress = None
        while True:
            progress = get_indexing_progress()
            status = get_indexing_status()

            # Only send if progress changed
            if progress != last_progress:
                event_data = {
                    "status": status["status"],
                    "message": status["message"],
                    "progress": progress
                }
                yield f"data: {json.dumps(event_data)}\n\n"
                last_progress = progress.copy() if progress else None

            # Stop if indexing is complete or failed
            if status["status"] in ["completed", "failed"]:
                # Send final event
                event_data = {
                    "status": status["status"],
                    "message": status["message"],
                    "progress": progress,
                    "done": True
                }
                yield f"data: {json.dumps(event_data)}\n\n"
                break

            await asyncio.sleep(0.5)  # Poll every 500ms

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============== Indexing Endpoints ==============

@router.post("/index", response_model=IndexResponse, tags=["Indexing"])
async def index_documents(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Index documents into HippoRAG (async).

    This endpoint indexes the provided documents in the background,
    allowing the request to return immediately.
    Use /index/progress SSE endpoint to track progress.
    """
    if get_indexing_status()["status"] == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    if not request.docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    def run_indexing_with_progress(docs: List[str]):
        try:
            reset_indexing_progress()
            set_indexing_progress(total_docs=len(docs), current_stage="starting")
            set_indexing_status("indexing", f"Indexing {len(docs)} documents...")

            hipporag = get_hipporag()

            # Stage 1: Chunk embedding
            set_indexing_progress(
                current_stage="embedding_chunks",
                processed_docs=1 if len(docs) > 0 else 0,
            )
            hipporag.index(docs=docs)

            set_indexing_progress(current_stage="completed", processed_docs=len(docs))
            set_indexing_status("completed", f"Successfully indexed {len(docs)} documents")
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            set_indexing_progress(current_stage="failed", error=str(e))
            set_indexing_status("failed", str(e))

    background_tasks.add_task(run_indexing_with_progress, request.docs)

    return IndexResponse(
        status="accepted",
        message=f"Started indexing {len(request.docs)} documents. Use /index/progress for real-time updates.",
        num_docs=len(request.docs)
    )


@router.post("/index/upload", response_model=IndexResponse, tags=["Indexing"])
async def index_from_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Index documents from an uploaded file (async).

    Supports .txt, .md, .json, .jsonl files.
    For .txt/.md: each line or paragraph is a document.
    For .json: expects array of strings or array of {content: str} objects.
    For .jsonl: each line is a document or {content: str} object.

    Use /index/progress SSE endpoint to track progress.
    """

    if get_indexing_status()["status"] == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    content = await file.read()
    filename = file.filename or "unknown.txt"

    try:
        docs = parse_upload_bytes_to_docs(content, filename)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not docs:
        raise HTTPException(status_code=400, detail="No valid documents found in file")

    def run_indexing_with_progress(docs: List[str]):
        try:
            reset_indexing_progress()
            set_indexing_progress(total_docs=len(docs), current_stage="starting")
            set_indexing_status("indexing", f"Indexing {len(docs)} documents from file...")

            hipporag = get_hipporag()
            set_indexing_progress(
                current_stage="embedding_chunks",
                processed_docs=1 if len(docs) > 0 else 0,
            )
            hipporag.index(docs=docs)

            set_indexing_progress(current_stage="completed", processed_docs=len(docs))
            set_indexing_status("completed", f"Successfully indexed {len(docs)} documents")
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            set_indexing_progress(current_stage="failed", error=str(e))
            set_indexing_status("failed", str(e))

    background_tasks.add_task(run_indexing_with_progress, docs)

    return IndexResponse(
        status="accepted",
        message=f"Started indexing {len(docs)} documents from {file.filename}. Use /index/progress for real-time updates.",
        num_docs=len(docs)
    )


@router.post("/index/sync", response_model=IndexResponse, tags=["Indexing"])
async def index_documents_sync(request: IndexRequest):
    """
    Index documents into HippoRAG (synchronous).

    This endpoint indexes the provided documents and waits for completion.
    Use this for small document sets or when you need confirmation.
    """
    if get_indexing_status()["status"] == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    if not request.docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    try:
        set_indexing_status("indexing", f"Indexing {len(request.docs)} documents...")
        hipporag = get_hipporag()
        hipporag.index(docs=request.docs)
        set_indexing_status("completed", f"Successfully indexed {len(request.docs)} documents")

        return IndexResponse(
            status="completed",
            message=f"Successfully indexed {len(request.docs)} documents",
            num_docs=len(request.docs)
        )
    except Exception as e:
        set_indexing_status("failed", str(e))
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


# ============== Retrieval Endpoints ==============

def convert_query_solution_to_result(qs, query: str, return_scores: bool = False) -> QueryResult:
    """Convert a QuerySolution object to a QueryResult model."""
    passages = []
    # QuerySolution has 'docs' (List[str]) not 'passages'
    if hasattr(qs, 'docs') and qs.docs:
        for doc in qs.docs:
            # docs are strings, not objects
            passages.append(Passage(
                content=str(doc),
                doc_id=None
            ))

    scores = None
    if return_scores and hasattr(qs, 'doc_scores') and qs.doc_scores is not None:
        import numpy as np
        if isinstance(qs.doc_scores, np.ndarray):
            scores = qs.doc_scores.tolist()

    return QueryResult(
        query=qs.question if hasattr(qs, 'question') else query,
        passages=passages,
        scores=scores
    )


@router.post("/retrieve", response_model=RetrieveResponse, tags=["Retrieval"])
async def retrieve(request: RetrieveRequest):
    """
    Retrieve relevant passages for queries using HippoRAG.

    Uses the graph-based HippoRAG retrieval method for multi-hop reasoning.
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    try:
        hipporag = get_hipporag()

        results = hipporag.retrieve(
            queries=request.queries,
            num_to_retrieve=request.num_to_retrieve
        )

        # Handle both with and without metrics
        if isinstance(results, tuple):
            query_solutions, metrics = results
        else:
            query_solutions = results
            metrics = None

        # Convert to response format
        response_results = []
        for i, qs in enumerate(query_solutions):
            result = convert_query_solution_to_result(
                qs,
                request.queries[i],
                request.return_scores
            )
            response_results.append(result)

        return RetrieveResponse(results=response_results, metrics=metrics)

    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.post("/retrieve/dpr", response_model=RetrieveResponse, tags=["Retrieval"])
async def retrieve_dpr(request: DPRRequest):
    """
    Retrieve relevant passages using standard DPR (Dense Passage Retrieval).

    Uses standard vector similarity search without graph-based reasoning.
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    try:
        hipporag = get_hipporag()

        results = hipporag.retrieve_dpr(
            queries=request.queries,
            num_to_retrieve=request.num_to_retrieve
        )

        # Handle both with and without metrics
        if isinstance(results, tuple):
            query_solutions, metrics = results
        else:
            query_solutions = results
            metrics = None

        # Convert to response format
        response_results = []
        for i, qs in enumerate(query_solutions):
            result = convert_query_solution_to_result(qs, request.queries[i], True)
            response_results.append(result)

        return RetrieveResponse(results=response_results, metrics=metrics)

    except Exception as e:
        logger.error(f"DPR retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"DPR retrieval failed: {str(e)}")


# ============== QA Endpoints ==============

@router.post("/qa", response_model=QAResponse, tags=["Question Answering"])
async def question_answering(request: QARequest):
    """
    Answer questions using HippoRAG RAG pipeline.

    Performs graph-based retrieval and then uses an LLM to generate answers.
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    try:
        hipporag = get_hipporag()

        # First retrieve relevant passages
        retrieve_results = hipporag.retrieve(
            queries=request.queries,
            num_to_retrieve=request.num_to_retrieve
        )

        # Handle both with and without metrics
        if isinstance(retrieve_results, tuple):
            query_solutions, _ = retrieve_results
        else:
            query_solutions = retrieve_results

        # Then perform QA
        qa_results = hipporag.rag_qa(queries=query_solutions)

        # Handle different return formats
        if isinstance(qa_results, tuple):
            if len(qa_results) >= 3:
                query_solutions, answers, qa_metrics = qa_results[0], qa_results[1], qa_results[2]
            else:
                query_solutions, answers = qa_results[0], qa_results[1]
                qa_metrics = None
        else:
            answers = qa_results
            qa_metrics = None

        # Ensure metrics is a dict or None (not a list)
        if qa_metrics is not None and not isinstance(qa_metrics, dict):
            qa_metrics = None

        # Convert to response format
        response_results = []
        for i, qs in enumerate(query_solutions):
            passages = []
            # QuerySolution has 'docs' (List[str]) not 'passages'
            if hasattr(qs, 'docs') and qs.docs:
                for doc in qs.docs:
                    passages.append(Passage(
                        content=str(doc),
                        doc_id=None
                    ))

            response_results.append(QAResult(
                query=qs.question if hasattr(qs, 'question') else request.queries[i],
                answer=answers[i] if i < len(answers) else "",
                passages=passages
            ))

        return QAResponse(results=response_results, metrics=qa_metrics)

    except Exception as e:
        logger.error(f"QA failed: {e}")
        raise HTTPException(status_code=500, detail=f"QA failed: {str(e)}")


@router.post("/qa/dpr", response_model=QAResponse, tags=["Question Answering"])
async def question_answering_dpr(request: DPRQARequest):
    """
    Answer questions using standard DPR RAG pipeline.

    Uses DPR retrieval followed by LLM-based answer generation.
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    try:
        hipporag = get_hipporag()

        # First retrieve relevant passages
        retrieve_results = hipporag.retrieve_dpr(
            queries=request.queries,
            num_to_retrieve=request.num_to_retrieve
        )

        # Handle both with and without metrics
        if isinstance(retrieve_results, tuple):
            query_solutions, _ = retrieve_results
        else:
            query_solutions = retrieve_results

        # Then perform QA
        qa_results = hipporag.rag_qa_dpr(queries=query_solutions)

        # Handle different return formats
        if isinstance(qa_results, tuple):
            if len(qa_results) >= 3:
                query_solutions, answers, qa_metrics = qa_results[0], qa_results[1], qa_results[2]
            else:
                query_solutions, answers = qa_results[0], qa_results[1]
                qa_metrics = None
        else:
            answers = qa_results
            qa_metrics = None

        # Ensure metrics is a dict or None (not a list)
        if qa_metrics is not None and not isinstance(qa_metrics, dict):
            qa_metrics = None

        # Convert to response format
        response_results = []
        for i, qs in enumerate(query_solutions):
            passages = []
            # QuerySolution has 'docs' (List[str]) not 'passages'
            if hasattr(qs, 'docs') and qs.docs:
                for doc in qs.docs:
                    passages.append(Passage(
                        content=str(doc),
                        doc_id=None
                    ))

            response_results.append(QAResult(
                query=qs.question if hasattr(qs, 'question') else request.queries[i],
                answer=answers[i] if i < len(answers) else "",
                passages=passages
            ))

        return QAResponse(results=response_results, metrics=qa_metrics)

    except Exception as e:
        logger.error(f"DPR QA failed: {e}")
        raise HTTPException(status_code=500, detail=f"DPR QA failed: {str(e)}")


# ============== Multi-Tenancy: Book Endpoints ==============

@router.post("/book/index", response_model=BookIndexResponse, tags=["Book Indexing"])
async def index_book_async(request: BookIndexRequest, background_tasks: BackgroundTasks):
    """
    Index documents into a specific book (async).

    Returns immediately; use GET /index/progress (SSE) for progress, same as POST /index.
    """
    if get_indexing_status()["status"] == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    if not request.docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    if not request.book_id:
        raise HTTPException(status_code=400, detail="book_id is required")

    book_id = request.book_id
    docs = request.docs

    def run_book_indexing():
        try:
            reset_indexing_progress()
            set_indexing_progress(total_docs=len(docs), current_stage="starting")
            set_indexing_status("indexing", f"Indexing {len(docs)} documents into book {book_id}...")

            manager = get_multi_tenancy_manager()
            set_indexing_progress(
                current_stage="embedding_chunks",
                processed_docs=1 if len(docs) > 0 else 0,
            )
            result = manager.index_book(book_id, docs)

            if result.get("status") == "failed":
                set_indexing_progress(current_stage="failed", error=result.get("message", "unknown"))
                set_indexing_status("failed", result["message"])
            else:
                set_indexing_progress(current_stage="completed", processed_docs=len(docs))
                set_indexing_status("completed", result["message"])
        except Exception as e:
            logger.error(f"Book indexing failed: {e}")
            set_indexing_progress(current_stage="failed", error=str(e))
            set_indexing_status("failed", str(e))

    background_tasks.add_task(run_book_indexing)

    return BookIndexResponse(
        status="accepted",
        message=(
            f"Started indexing {len(docs)} documents into book {book_id}. "
            "Use /index/progress for real-time updates."
        ),
        book_id=book_id,
        num_docs=len(docs),
    )


@router.post("/book/index/upload", response_model=BookIndexResponse, tags=["Book Indexing"])
async def index_book_from_file(
    background_tasks: BackgroundTasks,
    book_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Index documents from an uploaded file into a specific book (async).

    Same file formats as POST /index/upload. Prefer this over POST /book/index with a JSON
    body for large files — avoids serializing millions of strings in the client request.
    """
    if get_indexing_status()["status"] == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    if not book_id.strip():
        raise HTTPException(status_code=400, detail="book_id is required")

    content = await file.read()
    filename = file.filename or "unknown.txt"

    try:
        docs = parse_upload_bytes_to_docs(content, filename)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not docs:
        raise HTTPException(status_code=400, detail="No valid documents found in file")

    book_id_clean = book_id.strip()

    def run_book_indexing():
        try:
            reset_indexing_progress()
            set_indexing_progress(total_docs=len(docs), current_stage="starting")
            set_indexing_status(
                "indexing",
                f"Indexing {len(docs)} documents into book {book_id_clean} (from {filename})...",
            )

            manager = get_multi_tenancy_manager()
            set_indexing_progress(
                current_stage="embedding_chunks",
                processed_docs=1 if len(docs) > 0 else 0,
            )
            result = manager.index_book(book_id_clean, docs)

            if result.get("status") == "failed":
                set_indexing_progress(current_stage="failed", error=result.get("message", "unknown"))
                set_indexing_status("failed", result["message"])
            else:
                set_indexing_progress(current_stage="completed", processed_docs=len(docs))
                set_indexing_status("completed", result["message"])
        except Exception as e:
            logger.error(f"Book indexing failed: {e}")
            set_indexing_progress(current_stage="failed", error=str(e))
            set_indexing_status("failed", str(e))

    background_tasks.add_task(run_book_indexing)

    return BookIndexResponse(
        status="accepted",
        message=(
            f"Started indexing {len(docs)} documents into book {book_id_clean} from {filename}. "
            "Use /index/progress for real-time updates."
        ),
        book_id=book_id_clean,
        num_docs=len(docs),
    )


@router.post("/book/index/sync", response_model=BookIndexResponse, tags=["Book Indexing"])
async def index_book_sync(request: BookIndexRequest):
    """
    Index documents into a specific book (synchronous).

    This endpoint indexes documents into the specified book and waits for completion.
    Each book is an independent data unit that can be shared across multiple businesses.
    """
    if not request.docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    if not request.book_id:
        raise HTTPException(status_code=400, detail="book_id is required")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.index_book(request.book_id, request.docs)

        if result['status'] == 'failed':
            raise HTTPException(status_code=500, detail=result['message'])

        return BookIndexResponse(
            status=result['status'],
            message=result['message'],
            book_id=result['book_id'],
            num_docs=result['num_docs']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Book indexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Book indexing failed: {str(e)}")


@router.get("/books", response_model=BooksListResponse, tags=["Book Management"])
async def list_books():
    """
    List all books in the system.

    Returns metadata for all books including document counts and status.
    """
    try:
        manager = get_multi_tenancy_manager()
        books = manager.list_books()
        return BooksListResponse(
            books=[BookInfo(**book) for book in books]
        )
    except Exception as e:
        logger.error(f"Failed to list books: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list books: {str(e)}")


@router.delete("/book", response_model=BookDeleteResponse, tags=["Book Management"])
async def delete_book(book_id: str):
    """
    Delete a book and all its data.

    This removes the book, its embeddings, graph data, and all business bindings.
    This operation cannot be undone.
    """
    if not book_id:
        raise HTTPException(status_code=400, detail="book_id is required")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.delete_book(book_id)

        if result['status'] == 'not_found':
            raise HTTPException(status_code=404, detail=result['message'])

        return BookDeleteResponse(
            status=result['status'],
            message=result['message']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete book: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete book: {str(e)}")


# ============== Multi-Tenancy: Business Binding Endpoints ==============

@router.post("/business/bind", response_model=BusinessBindResponse, tags=["Business Management"])
async def bind_books_to_business(request: BusinessBindRequest):
    """
    Bind books to a business.

    This creates a many-to-many relationship between businesses and books.
    A business can access all books bound to it for queries.
    """
    if not request.business_id:
        raise HTTPException(status_code=400, detail="business_id is required")

    if not request.book_ids:
        raise HTTPException(status_code=400, detail="book_ids is required")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.bind_books(request.business_id, request.book_ids)

        if result['status'] == 'failed':
            raise HTTPException(status_code=500, detail=result['message'])

        return BusinessBindResponse(
            status=result['status'],
            message=result['message'],
            business_id=result['business_id'],
            book_ids=result['book_ids']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bind books: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to bind books: {str(e)}")


@router.post("/business/unbind", response_model=BusinessBindResponse, tags=["Business Management"])
async def unbind_books_from_business(request: BusinessUnbindRequest):
    """
    Unbind books from a business.

    This removes the relationship between a business and specified books.
    The books themselves are not deleted.
    """
    if not request.business_id:
        raise HTTPException(status_code=400, detail="business_id is required")

    if not request.book_ids:
        raise HTTPException(status_code=400, detail="book_ids is required")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.unbind_books(request.business_id, request.book_ids)

        if result['status'] == 'failed':
            raise HTTPException(status_code=500, detail=result['message'])

        return BusinessBindResponse(
            status=result['status'],
            message=result['message'],
            business_id=result['business_id'],
            book_ids=[]  # Return empty list for unbind
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unbind books: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to unbind books: {str(e)}")


@router.get("/business/books", response_model=BusinessBooksResponse, tags=["Business Management"])
async def get_business_books(business_id: str):
    """
    List all books bound to a business.

    Returns metadata for all books that the specified business can access.
    """
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id is required")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.get_business_books(business_id)

        return BusinessBooksResponse(
            business_id=result['business_id'],
            books=[BookInfo(**book) for book in result['books']]
        )
    except Exception as e:
        logger.error(f"Failed to get business books: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get business books: {str(e)}")


# ============== Multi-Tenancy: Business Query Endpoints ==============

@router.post("/business/retrieve", response_model=BusinessRetrieveResponse, tags=["Business Query"])
async def retrieve_by_business(request: BusinessRetrieveRequest):
    """
    Retrieve passages from all books bound to a business.

    Searches across all books that the business has access to and returns
    combined results.
    """
    if not request.business_id:
        raise HTTPException(status_code=400, detail="business_id is required")

    if not request.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.retrieve_by_business(
            business_id=request.business_id,
            queries=request.queries,
            num_to_retrieve=request.num_to_retrieve,
            return_scores=request.return_scores
        )

        response_results = []
        for r in result['results']:
            passages = [
                BusinessPassage(**p) for p in r['passages']
            ]
            response_results.append(BusinessQueryResult(
                query=r['query'],
                passages=passages,
                scores=r.get('scores')
            ))

        return BusinessRetrieveResponse(
            results=response_results,
            business_id=result['business_id'],
            books_searched=result['books_searched']
        )
    except Exception as e:
        logger.error(f"Business retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Business retrieval failed: {str(e)}")


@router.post("/business/qa", response_model=BusinessQAResponse, tags=["Business Query"])
async def qa_by_business(request: BusinessQARequest):
    """
    Answer questions using all books bound to a business.

    Performs retrieval across all accessible books and generates answers
    using the combined context.
    """
    if not request.business_id:
        raise HTTPException(status_code=400, detail="business_id is required")

    if not request.queries:
        raise HTTPException(status_code=400, detail="No queries provided")

    try:
        manager = get_multi_tenancy_manager()
        result = manager.qa_by_business(
            business_id=request.business_id,
            queries=request.queries,
            num_to_retrieve=request.num_to_retrieve
        )

        response_results = []
        for r in result['results']:
            passages = [
                BusinessPassage(**p) for p in r['passages']
            ]
            response_results.append(BusinessQAResult(
                query=r['query'],
                answer=r['answer'],
                passages=passages,
                book_id=r.get('book_id')
            ))

        return BusinessQAResponse(
            results=response_results,
            business_id=result['business_id'],
            books_searched=result['books_searched']
        )
    except Exception as e:
        logger.error(f"Business QA failed: {e}")
        raise HTTPException(status_code=500, detail=f"Business QA failed: {str(e)}")


# ============== Book Management Endpoints ==============

@router.post("/book", response_model=BookCreateResponse, tags=["Book Management"])
async def create_book(request: BookCreateRequest):
    """
    Create a new book record explicitly.
    """
    if not request.book_id:
        raise HTTPException(status_code=400, detail="book_id is required")
    try:
        manager = get_multi_tenancy_manager()
        result = manager.create_book(request.book_id)
        if result:
            return BookCreateResponse(
                status="created",
                message=f"Book {request.book_id} created successfully",
                book_id=request.book_id
            )
        else:
            return BookCreateResponse(
                status="exists",
                message=f"Book {request.book_id} already exists",
                book_id=request.book_id
            )
    except Exception as e:
        logger.error(f"Book creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Book creation failed: {str(e)}")


# ============== Business Management Endpoints ==============
@router.post("/business", response_model=BusinessCreateResponse, tags=["Business Management"])
async def create_business(request: BusinessCreateRequest):
    """
    Create a new business record.
    """
    if not request.business_id:
        raise HTTPException(status_code=400, detail="business_id is required")
    try:
        manager = get_multi_tenancy_manager()
        result = manager.create_business(
            business_id=request.business_id,
            name=request.name,
            description=request.description
        )
        if result:
            return BusinessCreateResponse(
                status="created",
                message=f"Business {request.business_id} created successfully",
                business_id=request.business_id
            )
        else:
            return BusinessCreateResponse(
                status="exists",
                message=f"Business {request.business_id} already exists",
                business_id=request.business_id
            )
    except Exception as e:
        logger.error(f"Business creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Business creation failed: {str(e)}")


@router.get("/business/{business_id}", response_model=BusinessInfo, tags=["Business Management"])
async def get_business(business_id: str):
    """
    Get business information.
    """
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id is required")
    try:
        manager = get_multi_tenancy_manager()
        result = manager.get_business(business_id)
        if result:
            return BusinessInfo(
                business_id=result['business_id'],
                name=result.get('name'),
                description=result.get('description'),
                book_count=result.get('book_count', 0),
                status=result.get('status', 'active'),
                created_at=result.get('created_at'),
                updated_at=result.get('updated_at')
            )
        else:
            raise HTTPException(status_code=404, detail=f"Business {business_id} not found")
    except Exception as e:
        logger.error(f"Get business failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get business failed: {str(e)}")


@router.get("/businesses", response_model=BusinessesListResponse, tags=["Business Management"])
async def list_businesses():
    """
    List all businesses.
    """
    try:
        manager = get_multi_tenancy_manager()
        businesses = manager.list_businesses()
        business_infos = [
            BusinessInfo(
                business_id=b['business_id'],
                name=b.get('name'),
                description=b.get('description'),
                book_count=b.get('book_count', 0),
                status=b.get('status', 'active'),
                created_at=b.get('created_at'),
                updated_at=b.get('updated_at')
            )
            for b in businesses
        ]
        return BusinessesListResponse(businesses=business_infos)
    except Exception as e:
        logger.error(f"List businesses failed: {e}")
        raise HTTPException(status_code=500, detail=f"List businesses failed: {str(e)}")


@router.put("/business/{business_id}", response_model=BusinessUpdateResponse, tags=["Business Management"])
async def update_business(business_id: str, request: BusinessUpdateRequest):
    """
    Update business information.
    """
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id is required")
    try:
        manager = get_multi_tenancy_manager()
        result = manager.update_business(
            business_id=business_id,
            name=request.name,
            description=request.description
        )
        if result:
            return BusinessUpdateResponse(
                status="updated",
                message=f"Business {business_id} updated successfully",
                business_id=business_id
            )
        else:
            raise HTTPException(status_code=404, detail=f"Business {business_id} not found")
    except Exception as e:
        logger.error(f"Update business failed: {e}")
        raise HTTPException(status_code=500, detail=f"Update business failed: {str(e)}")
@router.delete("/business/{business_id}", response_model=BusinessDeleteResponse, tags=["Business Management"])
async def delete_business(business_id: str):
    """
    Delete a business and all its bindings.
    """
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id is required")
    try:
        manager = get_multi_tenancy_manager()
        result = manager.delete_business(business_id)
        if result:
            return BusinessDeleteResponse(
                status="deleted",
                message=f"Business {business_id} deleted successfully"
            )
        else:
            raise HTTPException(status_code=404, detail=f"Business {business_id} not found")
    except Exception as e:
        logger.error(f"Delete business failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete business failed: {str(e)}")
