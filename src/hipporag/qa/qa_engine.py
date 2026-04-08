import json
import logging
import os
import time
from typing import List, Dict, Tuple
from tqdm import tqdm

from ..utils.config_utils import BaseConfig
from ..llm import BaseLLM
from ..prompts.prompt_template_manager import PromptTemplateManager
from ..utils.misc_utils import QuerySolution

logger = logging.getLogger(__name__)

_DEBUG_QA_DIR = os.path.join(os.getcwd(), "debug_json")


def _dump_qa_interaction(query: str, messages: list, response: str, metadata: dict):
    """Dump QA prompt and response to file for debugging."""
    os.makedirs(_DEBUG_QA_DIR, exist_ok=True)
    filename = f"qa_{int(time.time() * 1000)}.json"
    filepath = os.path.join(_DEBUG_QA_DIR, filename)
    data = {
        "query": query,
        "messages": messages,
        "response": response,
        "metadata": metadata,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Dumped QA interaction to {filepath}")


class QAEngine:
    """
    Handles question-answering operations.

    def __init__(self,
                 global_config: BaseConfig,
                 llm_model: BaseLLM,
                 prompt_template_manager: PromptTemplateManager):
        """
        Initialize QAEngine.

        Args:
            global_config: Global configuration
            llm_model: LLM model instance
            prompt_template_manager: Prompt template manager
        """
        self.global_config = global_config
        self.llm_model = llm_model
        self.prompt_template_manager = prompt_template_manager

    def qa(self, queries: List[QuerySolution]) -> Tuple[List[QuerySolution], List[str], List[Dict]]:
        """
        Executes question-answering (QA) inference using a provided set of query solutions and a language model.

        Parameters:
            queries: List[QuerySolution]
                A list of QuerySolution objects that contain the user queries, retrieved documents, and other related information.

        Returns:
            Tuple[List[QuerySolution], List[str], List[Dict]]
                A tuple containing:
                - A list of updated QuerySolution objects with the predicted answers embedded in them.
                - A list of raw response messages from the language model.
                - A list of metadata dictionaries associated with the results.
        """
        # Running inference for QA
        all_qa_messages = []

        for query_solution in tqdm(queries, desc="Collecting QA prompts"):

            # obtain the retrieved docs
            retrieved_passages = query_solution.docs[:self.global_config.qa_top_k]

            prompt_user = ''
            for passage in retrieved_passages:
                prompt_user += f'Wikipedia Title: {passage}\n\n'
            prompt_user += 'Question: ' + query_solution.question + '\nThought: '

            if self.prompt_template_manager.is_template_name_valid(name=f'rag_qa_{self.global_config.dataset}'):
                # find the corresponding prompt for this dataset
                prompt_dataset_name = self.global_config.dataset
            else:
                # the dataset does not have a customized prompt template yet
                logger.debug(
                    f"rag_qa_{self.global_config.dataset} does not have a customized prompt template. Using MUSIQUE's prompt template instead.")
                prompt_dataset_name = 'musique'
            all_qa_messages.append(
                self.prompt_template_manager.render(name=f'rag_qa_{prompt_dataset_name}', prompt_user=prompt_user))

        all_qa_results = [self.llm_model.infer(qa_messages) for qa_messages in tqdm(all_qa_messages, desc="QA Reading")]

        all_response_message, all_metadata, all_cache_hit = zip(*all_qa_results)
        all_response_message, all_metadata = list(all_response_message), list(all_metadata)

        # Process responses and extract predicted answers.
        queries_solutions = []
        for query_solution_idx, query_solution in tqdm(enumerate(queries), desc="Extraction Answers from LLM Response"):
            response_content = all_response_message[query_solution_idx]
            metadata = all_metadata[query_solution_idx]
            qa_messages = all_qa_messages[query_solution_idx]

            # Dump QA prompt and response for debugging
            _dump_qa_interaction(
                query=query_solution.question,
                messages=qa_messages,
                response=response_content,
                metadata=metadata,
            )

            try:
                pred_ans = response_content.split('Answer:')[1].strip()
            except Exception as e:
                logger.warning(f"Error in parsing the answer from the raw LLM QA inference response: {str(e)}!")
                logger.warning(f"  Query: {query_solution.question}")
                logger.warning(f"  Raw response (first 500 chars): {response_content[:500]}")
                pred_ans = response_content

            query_solution.answer = pred_ans
            queries_solutions.append(query_solution)

        return queries_solutions, all_response_message, all_metadata
