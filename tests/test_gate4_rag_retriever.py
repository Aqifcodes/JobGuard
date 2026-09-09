from rag.retriever import RAGRetriever


def main():
    retriever = RAGRetriever(top_k=5)

    query = """
    The recruiter contacted me on WhatsApp and asked me to pay
    a refundable security deposit through UPI before joining the job.
    """

    results = retriever.retrieve(query)

    print("\n" + "=" * 70)
    print("GATE 4 — SEMANTIC RETRIEVAL TEST")
    print("=" * 70)

    print(f"\nQuery:\n{query.strip()}")

    print("\nRetrieved evidence:\n")

    for i, result in enumerate(results, start=1):
        print(f"--- Result {i} ---")
        print(f"Document ID: {result['document_id']}")
        print(f"Title: {result['title']}")
        print(f"Scam Type: {result['scam_type']}")
        print(f"Similarity: {result['similarity_score']:.4f}")
        print(f"Content: {result['content']}")
        print()


if __name__ == "__main__":
    main()