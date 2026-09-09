import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

KNOWLEDGE_BASE_FILE = DATA_DIR / "knowledge_base.json"
DOCUMENTS_FILE = DATA_DIR / "documents.json"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.npy"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def load_knowledge_base():
    """Load the Indian job-scam knowledge base."""

    with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
        documents = json.load(f)

    if not isinstance(documents, list):
        raise ValueError("Knowledge base must contain a JSON list.")

    if not documents:
        raise ValueError("Knowledge base is empty.")

    return documents


def create_embeddings(documents):
    """Create semantic embeddings for every knowledge-base document."""

    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = [
        f"{document['title']}. {document['content']}"
        for document in documents
    ]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    return embeddings


def save_documents(documents):
    """Save the documents used by the retriever."""

    with open(DOCUMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)


def save_embeddings(embeddings):
    """Save document embeddings as a NumPy array."""

    np.save(EMBEDDINGS_FILE, embeddings)


def main():
    print("Loading Indian job-scam knowledge base...")

    documents = load_knowledge_base()

    print(f"Loaded {len(documents)} knowledge documents.")

    print(f"Creating embeddings using {EMBEDDING_MODEL}...")

    embeddings = create_embeddings(documents)

    if len(documents) != len(embeddings):
        raise ValueError(
            "Number of documents does not match number of embeddings."
        )

    save_documents(documents)
    save_embeddings(embeddings)

    print("\nRAG ingestion completed.")
    print(f"Documents saved to: {DOCUMENTS_FILE}")
    print(f"Embeddings saved to: {EMBEDDINGS_FILE}")
    print(f"Embedding shape: {embeddings.shape}")


if __name__ == "__main__":
    main()