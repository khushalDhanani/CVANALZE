from unittest.mock import patch

from app.services.embedding_service import EmbeddingService, get_embedding


def test_embedding_similarity_comparison():
    text1 = "Flutter Developer"
    text2 = "Mobile App Developer using Flutter"
    text3 = "Plant Maintenance Executive"

    vectors = {
        text1: [1.0, 0.0] + [0.0] * 766,
        text2: [0.9, 0.1] + [0.0] * 766,
        text3: [0.0, 1.0] + [0.0] * 766,
    }
    with patch.object(EmbeddingService, "generate_embedding", side_effect=lambda text, **_: vectors[text]):
        emb1 = get_embedding(text1)
        emb2 = get_embedding(text2)
        emb3 = get_embedding(text3)

    assert emb1 is not None and len(emb1) == 768
    assert emb2 is not None and len(emb2) == 768
    assert emb3 is not None and len(emb3) == 768

    sim_flutter_mobile = EmbeddingService.cosine_similarity(emb1, emb2)
    sim_flutter_plant = EmbeddingService.cosine_similarity(emb1, emb3)

    print("\n[EMBEDDING SIMILARITY PROOF]")
    print(f"Similarity ('{text1}' vs '{text2}'): {sim_flutter_mobile:.6f}")
    print(f"Similarity ('{text1}' vs '{text3}'): {sim_flutter_plant:.6f}")

    assert sim_flutter_mobile > sim_flutter_plant, (
        f"Expected Flutter vs Mobile ({sim_flutter_mobile:.4f}) to be strictly higher than "
        f"Flutter vs Plant Maintenance ({sim_flutter_plant:.4f})"
    )


if __name__ == "__main__":
    test_embedding_similarity_comparison()
