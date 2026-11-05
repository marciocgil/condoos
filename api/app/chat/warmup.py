"""Download the embedding model at image build time: python -m app.chat.warmup"""

from app.chat.search import embed

if __name__ == "__main__":
    vectors = embed(["convenção do condomínio"])
    print(f"embedding model ready dims={len(vectors[0]) if vectors else 0}")
