"""
QA helper functions for HippoRAG.

Contains internal QA logic extracted from HippoRAG class.
"""
import logging
from typing import List, Dict, Optional, Tuple

from .utils.misc_utils import QuerySolution

logger = logging.getLogger(__name__)


class QAHelper:
    """
    Helper class for QA operations.

    Contains internal methods for:
    - Building QA prompts
    - Processing QA responses
    - Answer formatting
    """

    def __init__(self, config, llm, prompt_template_manager=None):
        """
        Initialize QA helper.

        Parameters:
            config: BaseConfig instance
            llm: LLM instance
            prompt_template_manager: Optional prompt template manager
        """
        self.config = config
        self.llm = llm
        self.prompt_template_manager = prompt_template_manager

    def build_qa_prompt(self, question: str, passages: List[str]) -> List[Dict[str, str]]:
        """
        Build prompt for QA.

        Parameters:
            question: The question to answer
            passages: Retrieved passages for context

        Returns:
            List of message dicts for LLM
        """
        # Build context from passages
        context = "\n\n".join([f"[{i+1}] {p}" for i, p in enumerate(passages)])

        # Use prompt template if available
        if self.prompt_template_manager:
            try:
                template = self.prompt_template_manager.get_template("rag_qa")
                system_prompt = template.get("system", "You are a helpful assistant.")
                user_prompt = template.get("user", "").replace("{context}", context).replace("{question}", question)
            except Exception:
                system_prompt = "You are a helpful assistant that answers questions based on the given context."
                user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nPlease answer based on the context above."
        else:
            system_prompt = "You are a helpful assistant that answers questions based on the given context."
            user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nPlease answer based on the context above."

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def generate_answer(self, question: str, passages: List[str]) -> Tuple[str, Dict]:
        """
        Generate answer for a question using passages.

        Parameters:
            question: The question to answer
            passages: Retrieved passages for context

        Returns:
            Tuple of (answer, metadata)
        """
        messages = self.build_qa_prompt(question, passages)

        response, metadata, _ = self.llm.infer(messages)

        return response, metadata

    def process_qa_results(
        self,
        queries: List[str],
        query_solutions: List[QuerySolution],
        answers: List[str]
    ) -> List[Dict]:
        """
        Process QA results into structured format.

        Parameters:
            queries: Original queries
            query_solutions: QuerySolution objects with passages
            answers: Generated answers

        Returns:
            List of result dicts
        """
        results = []
        for i, (query, qs, answer) in enumerate(zip(queries, query_solutions, answers)):
            passages = []
            if hasattr(qs, 'docs') and qs.docs:
                for doc in qs.docs:
                    passages.append({
                        "content": str(doc),
                        "doc_id": None
                    })

            results.append({
                "query": query,
                "answer": answer,
                "passages": passages
            })

        return results

    def format_response(
        self,
        results: List[Dict],
        metrics: Optional[Dict] = None
    ) -> Dict:
        """
        Format QA response.

        Parameters:
            results: List of QA results
            metrics: Optional metrics dict

        Returns:
            Formatted response dict
        """
        return {
            "results": results,
            "metrics": metrics
        }
