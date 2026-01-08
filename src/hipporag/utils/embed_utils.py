from typing import List
import numpy as np
from tqdm import tqdm


def retrieve_knn(query_ids: List[str], key_ids: List[str], query_vecs, key_vecs, k=2047, query_batch_size=1000,
                 key_batch_size=10000):
    """
    Retrieve the top-k nearest neighbors for each query id from the key ids.
    Args:
        query_ids:
        key_ids:
        k: top-k
        query_batch_size:
        key_batch_size:

    Returns:

    """
    if len(key_vecs) == 0: 
        return {}

    # Convert to numpy arrays if needed
    query_vecs = np.array(query_vecs, dtype=np.float32)
    key_vecs = np.array(key_vecs, dtype=np.float32)
    
    # Normalize vectors
    query_norms = np.linalg.norm(query_vecs, axis=1, keepdims=True)
    query_norms = np.where(query_norms == 0, 1, query_norms)  # Avoid division by zero
    query_vecs = query_vecs / query_norms
    
    key_norms = np.linalg.norm(key_vecs, axis=1, keepdims=True)
    key_norms = np.where(key_norms == 0, 1, key_norms)  # Avoid division by zero
    key_vecs = key_vecs / key_norms

    results = {}

    def get_batches(vecs, batch_size):
        for i in range(0, len(vecs), batch_size):
            yield vecs[i:i + batch_size], i

    for query_batch, query_batch_start_idx in tqdm(
            get_batches(vecs=query_vecs, batch_size=query_batch_size),
            total=(len(query_vecs) + query_batch_size - 1) // query_batch_size,  # Calculate total batches
            desc="KNN for Queries"
    ):
        batch_topk_sim_scores = []
        batch_topk_indices = []

        offset_keys = 0

        for key_batch, key_batch_start_idx in get_batches(vecs=key_vecs, batch_size=key_batch_size):
            actual_key_batch_size = key_batch.shape[0]

            # Compute similarity using matrix multiplication
            similarity = np.dot(query_batch, key_batch.T)

            # Get top-k for each query in the batch
            topk_size = min(k, actual_key_batch_size)
            # Get indices that would sort by similarity (descending)
            topk_indices_relative = np.argsort(similarity, axis=1)[:, -topk_size:][:, ::-1]
            topk_sim_scores = np.take_along_axis(similarity, topk_indices_relative, axis=1)
            
            # Adjust indices to account for offset
            topk_indices = topk_indices_relative + offset_keys

            batch_topk_sim_scores.append(topk_sim_scores)
            batch_topk_indices.append(topk_indices)

            offset_keys += actual_key_batch_size
        # end for each kb batch

        # Concatenate all batches
        batch_topk_sim_scores = np.concatenate(batch_topk_sim_scores, axis=1)
        batch_topk_indices = np.concatenate(batch_topk_indices, axis=1)

        # Get final top-k across all key batches
        final_topk_size = min(k, batch_topk_sim_scores.shape[1])
        final_topk_indices_relative = np.argsort(batch_topk_sim_scores, axis=1)[:, -final_topk_size:][:, ::-1]
        final_topk_sim_scores = np.take_along_axis(batch_topk_sim_scores, final_topk_indices_relative, axis=1)
        final_topk_indices = np.take_along_axis(batch_topk_indices, final_topk_indices_relative, axis=1)

        for i in range(final_topk_indices.shape[0]):
            query_relative_idx = query_batch_start_idx + i
            query_idx = query_ids[query_relative_idx]

            final_topk_indices_i = final_topk_indices[i]
            final_topk_sim_scores_i = final_topk_sim_scores[i]

            query_to_topk_key_ids = [key_ids[int(idx)] for idx in final_topk_indices_i]
            results[query_idx] = (query_to_topk_key_ids, final_topk_sim_scores_i.tolist())

    # end for each query batch

    return results
