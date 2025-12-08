from service.embedding_service import generate_embedding_by_paper_obj
from service.supabase_service import match_papers

paper_obj = {
        "title": "TKG-DM: Training-free Chroma Key Content Generation Diffusion Model",
        "keywords": ["chroma", "foreground", "background", "diffusion", "generation", "content"],
        "summary": "Diffusion models have enabled the generation of high-quality images..."
    }
embedding = generate_embedding_by_paper_obj(paper_obj)
print(embedding)

result = match_papers(embedding)
print(result)