"""
API routes for HippoRAG.

Defines all RESTful endpoints for indexing, retrieval, and QA operations.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, BackgroundTasks

from .models import (
    IndexRequest, IndexResponse,
    RetrieveRequest, RetrieveResponse, QueryResult, Passage,
    QARequest, QAResponse, QAResult,
    DPRRequest, DPRQARequest,
    HealthResponse, StatusResponse
)
from .dependencies import (
    get_hipporag, get_indexing_status, set_indexing_status, is_hipporag_initialized
)

logger = logging.getLogger(__name__)

router = APIRouter()


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


# ============== Indexing Endpoints ==============

@router.post("/index", response_model=IndexResponse, tags=["Indexing"])
async def index_documents(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Index documents into HippoRAG (async).

    This endpoint indexes the provided documents in the background,
    allowing the request to return immediately.
    """
    if get_indexing_status()["status"] == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    if not request.docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    def run_indexing(docs: List[str]):
        try:
            set_indexing_status("indexing", f"Indexing {len(docs)} documents...")
            hipporag = get_hipporag()
            hipporag.index(docs=docs)
            set_indexing_status("completed", f"Successfully indexed {len(docs)} documents")
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            set_indexing_status("failed", str(e))

    background_tasks.add_task(run_indexing, request.docs)

    return IndexResponse(
        status="accepted",
        message=f"Started indexing {len(request.docs)} documents in background",
        num_docs=len(request.docs)
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
