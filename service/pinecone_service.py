from pinecone import Pinecone

pc = Pinecone(host=os.getenv("PINECONE_HOST"), api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("paperembeddings")


def upsert_paper_embeddings(paper_embeddings: list[dict]):
    index.upsert(paper_embeddings)