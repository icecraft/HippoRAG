"""
Pydantic models for HippoRAG API request and response schemas.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============== Request Models ==============

class IndexRequest(BaseModel):
    """Request model for document indexing."""
    docs: List[str] = Field(..., description="List of documents to index")
    doc_ids: Optional[List[str]] = Field(None, description="Optional document IDs")


class RetrieveRequest(BaseModel):
    """Request model for retrieval."""
    queries: List[str] = Field(..., description="List of queries to retrieve")
    num_to_retrieve: Optional[int] = Field(None, description="Number of documents to retrieve per query")
    return_scores: bool = Field(False, description="Whether to return retrieval scores")


class QARequest(BaseModel):
    """Request model for question answering."""
    queries: List[str] = Field(..., description="List of questions to answer")
    num_to_retrieve: Optional[int] = Field(None, description="Number of documents to retrieve per query")


class DPRRequest(BaseModel):
    """Request model for DPR retrieval."""
    queries: List[str] = Field(..., description="List of queries to retrieve")
    num_to_retrieve: Optional[int] = Field(None, description="Number of documents to retrieve per query")


class DPRQARequest(BaseModel):
    """Request model for DPR QA."""
    queries: List[str] = Field(..., description="List of questions to answer")
    num_to_retrieve: Optional[int] = Field(None, description="Number of documents to retrieve per query")


# ============== Response Models ==============

class Passage(BaseModel):
    """Model for a retrieved passage."""
    content: str = Field(..., description="Passage content")
    doc_id: Optional[str] = Field(None, description="Document ID")


class QueryResult(BaseModel):
    """Model for a single query result."""
    query: str = Field(..., description="The query")
    passages: List[Passage] = Field(..., description="Retrieved passages")
    scores: Optional[List[float]] = Field(None, description="Retrieval scores")


class RetrieveResponse(BaseModel):
    """Response model for retrieval."""
    results: List[QueryResult] = Field(..., description="Retrieval results")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Retrieval metrics if available")


class QAResult(BaseModel):
    """Model for a single QA result."""
    query: str = Field(..., description="The question")
    answer: str = Field(..., description="The answer")
    passages: List[Passage] = Field(..., description="Retrieved passages used for answering")


class QAResponse(BaseModel):
    """Response model for question answering."""
    results: List[QAResult] = Field(..., description="QA results")
    metrics: Optional[Dict[str, Any]] = Field(None, description="QA metrics if available")


class IndexResponse(BaseModel):
    """Response model for document indexing."""
    status: str = Field(..., description="Indexing status")
    message: str = Field(..., description="Status message")
    num_docs: int = Field(..., description="Number of documents indexed")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Service status")
    hipporag_initialized: bool = Field(..., description="Whether HippoRAG is initialized")
    indexing_status: str = Field(..., description="Current indexing status")


class StatusResponse(BaseModel):
    """Response model for status check."""
    indexing_status: str = Field(..., description="Current indexing status")
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")


# ============== Multi-Tenancy Request Models ==============

class BookIndexRequest(BaseModel):
    """Request model for book indexing."""
    book_id: str = Field(..., description="Book identifier")
    docs: List[str] = Field(..., description="List of documents to index")


class BusinessBindRequest(BaseModel):
    """Request model for binding books to business."""
    business_id: str = Field(..., description="Business identifier")
    book_ids: List[str] = Field(..., description="List of book IDs to bind")


class BusinessUnbindRequest(BaseModel):
    """Request model for unbinding books from business."""
    business_id: str = Field(..., description="Business identifier")
    book_ids: List[str] = Field(..., description="List of book IDs to unbind")


class BusinessQARequest(BaseModel):
    """Request model for business QA."""
    business_id: str = Field(..., description="Business identifier")
    queries: List[str] = Field(..., description="List of questions to answer")
    num_to_retrieve: Optional[int] = Field(None, description="Number of documents to retrieve per query")


class BusinessRetrieveRequest(BaseModel):
    """Request model for business retrieval."""
    business_id: str = Field(..., description="Business identifier")
    queries: List[str] = Field(..., description="List of queries to retrieve")
    num_to_retrieve: Optional[int] = Field(None, description="Number of documents to retrieve per query")
    return_scores: bool = Field(False, description="Whether to return retrieval scores")


# ============== Multi-Tenancy Response Models ==============

class BookIndexResponse(BaseModel):
    """Response model for book indexing."""
    status: str = Field(..., description="Indexing status")
    message: str = Field(..., description="Status message")
    book_id: str = Field(..., description="Book identifier")
    num_docs: int = Field(..., description="Number of documents indexed")


class BookInfo(BaseModel):
    """Model for book information."""
    book_id: str = Field(..., description="Book identifier")
    doc_count: int = Field(..., description="Number of documents in book")
    status: str = Field(..., description="Book status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class BooksListResponse(BaseModel):
    """Response model for listing books."""
    books: List[BookInfo] = Field(..., description="List of books")


class BusinessBindResponse(BaseModel):
    """Response model for business binding."""
    status: str = Field(..., description="Binding status")
    message: str = Field(..., description="Status message")
    business_id: str = Field(..., description="Business identifier")
    book_ids: List[str] = Field(..., description="List of bound book IDs")


class BusinessBooksResponse(BaseModel):
    """Response model for business books."""
    business_id: str = Field(..., description="Business identifier")
    books: List[BookInfo] = Field(..., description="List of books bound to business")


class BusinessPassage(BaseModel):
    """Model for a passage with book_id."""
    content: str = Field(..., description="Passage content")
    doc_id: Optional[str] = Field(None, description="Document ID")
    book_id: Optional[str] = Field(None, description="Source book ID")


class BusinessQueryResult(BaseModel):
    """Model for a business query result."""
    query: str = Field(..., description="The query")
    passages: List[BusinessPassage] = Field(..., description="Retrieved passages")
    scores: Optional[List[float]] = Field(None, description="Retrieval scores")


class BusinessRetrieveResponse(BaseModel):
    """Response model for business retrieval."""
    results: List[BusinessQueryResult] = Field(..., description="Retrieval results")
    business_id: str = Field(..., description="Business identifier")
    books_searched: List[str] = Field(..., description="Book IDs that were searched")


class BusinessQAResult(BaseModel):
    """Model for a business QA result."""
    query: str = Field(..., description="The question")
    answer: str = Field(..., description="The answer")
    passages: List[BusinessPassage] = Field(..., description="Retrieved passages used for answering")
    book_id: Optional[str] = Field(None, description="Primary source book ID")


class BusinessQAResponse(BaseModel):
    """Response model for business QA."""
    results: List[BusinessQAResult] = Field(..., description="QA results")
    business_id: str = Field(..., description="Business identifier")
    books_searched: List[str] = Field(..., description="Book IDs that were searched")


class BookDeleteResponse(BaseModel):
    """Response model for book deletion."""
    status: str = Field(..., description="Deletion status")
    message: str = Field(..., description="Status message")
