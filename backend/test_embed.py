import asyncio
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

def main():
    settings.EMBEDDING_MODEL = "nomic-embed-text"
    
    # Let's verify nomic-embed-text is available in ollama first
    import httpx
    try:
        r = httpx.post(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/pull", json={"name": "nomic-embed-text"}, timeout=120.0)
        print("Pulled model:", r.status_code)
    except Exception as e:
        print("Failed to pull:", e)

    t1 = "Flutter Developer"
    t2 = "Mobile App Developer using Flutter"
    t3 = "Plant Maintenance Executive"

    print("Embedding T1...")
    emb1 = EmbeddingService.generate_embedding(t1, "nomic-embed-text")
    print("Embedding T2...")
    emb2 = EmbeddingService.generate_embedding(t2, "nomic-embed-text")
    print("Embedding T3...")
    emb3 = EmbeddingService.generate_embedding(t3, "nomic-embed-text")

    if not emb1 or not emb2 or not emb3:
        print("Failed to generate embeddings.")
        return

    sim_12 = EmbeddingService.cosine_similarity(emb1, emb2)
    sim_13 = EmbeddingService.cosine_similarity(emb1, emb3)

    print(f"Similarity ('{t1}' vs '{t2}'): {sim_12:.4f}")
    print(f"Similarity ('{t1}' vs '{t3}'): {sim_13:.4f}")

if __name__ == "__main__":
    main()
