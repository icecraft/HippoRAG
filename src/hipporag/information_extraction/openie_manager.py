import json
import os
import logging
from typing import List, Dict, Set, Tuple

from ..utils.config_utils import BaseConfig
from ..utils.misc_utils import NerRawOutput, TripleRawOutput, compute_mdhash_id

logger = logging.getLogger(__name__)


class OpenIEManager:
    """
    Manages OpenIE results loading, merging, and saving.
    """
    
    def __init__(self, 
                 global_config: BaseConfig,
                 openie_results_path: str):
        """
        Initialize OpenIEManager.
        
        Args:
            global_config: Global configuration
            openie_results_path: Path to save/load OpenIE results
        """
        self.global_config = global_config
        self.openie_results_path = openie_results_path
    
    def load_existing_openie(self, chunk_keys: List[str]) -> Tuple[List[dict], Set[str]]:
        """
        Loads existing OpenIE results from the specified file if it exists and combines
        them with new content while standardizing indices. If the file does not exist or
        is configured to be re-initialized from scratch with the flag `force_openie_from_scratch`,
        it prepares new entries for processing.

        Args:
            chunk_keys (List[str]): A list of chunk keys that represent identifiers
                                     for the content to be processed.

        Returns:
            Tuple[List[dict], Set[str]]: A tuple where the first element is the existing OpenIE
                                         information (if any) loaded from the file, and the
                                         second element is a set of chunk keys that still need to
                                         be saved or processed.
        """
        # combine openie_results with contents already in file, if file exists
        chunk_keys_to_save = set()

        if not self.global_config.force_openie_from_scratch and os.path.isfile(self.openie_results_path):
            openie_results = json.load(open(self.openie_results_path))
            all_openie_info = openie_results.get('docs', [])

            # Standardizing indices for OpenIE Files.
            renamed_openie_info = []
            for openie_info in all_openie_info:
                openie_info['idx'] = compute_mdhash_id(openie_info['passage'], 'chunk-')
                renamed_openie_info.append(openie_info)

            all_openie_info = renamed_openie_info

            existing_openie_keys = set([info['idx'] for info in all_openie_info])

            for chunk_key in chunk_keys:
                if chunk_key not in existing_openie_keys:
                    chunk_keys_to_save.add(chunk_key)
        else:
            all_openie_info = []
            chunk_keys_to_save = set(chunk_keys)

        return all_openie_info, chunk_keys_to_save
    
    def merge_openie_results(self,
                             all_openie_info: List[dict],
                             chunks_to_save: Dict[str, dict],
                             ner_results_dict: Dict[str, NerRawOutput],
                             triple_results_dict: Dict[str, TripleRawOutput]) -> List[dict]:
        """
        Merges OpenIE extraction results with corresponding passage and metadata.

        This function integrates the OpenIE extraction results, including named-entity
        recognition (NER) entities and triples, with their respective text passages
        using the provided chunk keys. The resulting merged data is appended to
        the `all_openie_info` list containing dictionaries with combined and organized
        data for further processing or storage.

        Parameters:
            all_openie_info (List[dict]): A list to hold dictionaries of merged OpenIE
                results and metadata for all chunks.
            chunks_to_save (Dict[str, dict]): A dict of chunk identifiers (keys) to process
                and merge OpenIE results to dictionaries with `hash_id` and `content` keys.
            ner_results_dict (Dict[str, NerRawOutput]): A dictionary mapping chunk keys
                to their corresponding NER extraction results.
            triple_results_dict (Dict[str, TripleRawOutput]): A dictionary mapping chunk
                keys to their corresponding OpenIE triple extraction results.

        Returns:
            List[dict]: The `all_openie_info` list containing dictionaries with merged
            OpenIE results, metadata, and the passage content for each chunk.
        """
        for chunk_key, row in chunks_to_save.items():
            passage = row['content']
            try:
                chunk_openie_info = {'idx': chunk_key, 'passage': passage,
                                 'extracted_entities': ner_results_dict[chunk_key].unique_entities,
                                 'extracted_triples': triple_results_dict[chunk_key].triples}
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_key}: {e}")
                chunk_openie_info = {'idx': chunk_key, 'passage': passage,
                                 'extracted_entities': [],
                                 'extracted_triples': []}
            all_openie_info.append(chunk_openie_info)

        return all_openie_info
    
    def save_openie_results(self, all_openie_info: List[dict]):
        """
        Computes statistics on extracted entities from OpenIE results and saves the aggregated data in a
        JSON file. The function calculates the average character and word lengths of the extracted entities
        and writes them along with the provided OpenIE information to a file.

        Parameters:
            all_openie_info : List[dict]
                List of dictionaries, where each dictionary represents information from OpenIE, including
                extracted entities.
        """
        sum_phrase_chars = sum([len(e) for chunk in all_openie_info for e in chunk['extracted_entities']])
        sum_phrase_words = sum([len(e.split()) for chunk in all_openie_info for e in chunk['extracted_entities']])
        num_phrases = sum([len(chunk['extracted_entities']) for chunk in all_openie_info])

        if len(all_openie_info) > 0:
            # Avoid division by zero if there are no phrases
            if num_phrases > 0:
                avg_ent_chars = round(sum_phrase_chars / num_phrases, 4)
                avg_ent_words = round(sum_phrase_words / num_phrases, 4)
            else:
                avg_ent_chars = 0
                avg_ent_words = 0
                
            openie_dict = {
                'docs': all_openie_info,
                'avg_ent_chars': avg_ent_chars,
                'avg_ent_words': avg_ent_words
            }
            
            with open(self.openie_results_path, 'w') as f:
                json.dump(openie_dict, f)
            logger.info(f"OpenIE results saved to {self.openie_results_path}")

