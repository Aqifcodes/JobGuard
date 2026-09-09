import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


class RAGRetriever:
    """
    Semantic retriever for the Indian job-scam knowledge base.

    This class only retrieves relevant evidence.
    It does not classify the investigation or produce a verdict.
    """

    def __init__(self, top_k=5):
        self.top_k = top_k

        base_dir = Path(__file__).resolve().parent
        data_dir = base_dir / "data"

        self.documents_file = data_dir / "documents.json"
        self.embeddings_file = data_dir / "embeddings.npy"

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.embeddings = np.load(self.embeddings_file)

        with open(self.documents_file, "r", encoding="utf-8") as f:
            self.documents = json.load(f)

        if len(self.documents) != len(self.embeddings):
            raise ValueError(
                "Number of documents does not match number of embeddings."
            )

        if self.embeddings.ndim != 2:
            raise ValueError(
                "Embeddings must be a 2-dimensional NumPy array."
            )

    def retrieve(self, query, top_k=None):
        """
        Retrieve the most semantically similar knowledge documents.

        Parameters:
            query: investigation text
            top_k: number of documents to retrieve

        Returns:
            Structured retrieval evidence.
        """

        if not isinstance(query, str) or not query.strip():
            return []

        k = top_k if top_k is not None else self.top_k
        k = min(k, len(self.documents))

        query_embedding = self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        similarities = np.dot(
            self.embeddings,
            query_embedding
        )

        top_indices = np.argsort(similarities)[-k:][::-1]

        results = []

        for index in top_indices:
            document = self.documents[int(index)]

            results.append(
                {
                    "document_id": document.get("id"),
                    "title": document.get("title"),
                    "content": document.get("content"),
                    "scam_type": document.get("scam_type"),
                    "source": document.get("source"),
                    "similarity_score": float(similarities[index])
                }
            )

        return results