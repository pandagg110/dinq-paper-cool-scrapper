from openai import OpenAI
import os
import requests
import json
proxies = {
    "http": "http://127.0.0.1:33210",
    "https": "http://127.0.0.1:33210",
}

# text-embedding-3-small => 1536 dims (fits IVFFLAT index limit)
EMBEDDING_MODEL = "text-embedding-3-small"


def generate_embedding(text: str):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    embedding = client.embeddings.create(
        # extra_headers={
        #     "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        #     "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
        # },
        model=EMBEDDING_MODEL,
        input=text,
        # input: ["text1", "text2", "text3"] # batch embeddings also supported!
        encoding_format="float"
    )

    return embedding.data[0].embedding

def generate_embedding_http(text: str, max_retries: int = 3, backoff: float = 1.0):
    import time

    api_key = os.getenv("OPENROUTER_API_KEY")
    retry = 0
    last_exception = None

    while retry < max_retries:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                proxies=proxies,
                json={
                    "model": "text-embedding-3-small",
                    "input": text,
                },
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            last_exception = e
            retry += 1
            if retry < max_retries:
                time.sleep(backoff * retry)
    raise last_exception



def generate_embedding_text(paper_obj: object):
    title = paper_obj.get("title")
    keywords = paper_obj.get("keywords")
    summary = paper_obj.get("summary")

    return f"Title: {title}\nKeywords: {keywords}\nSummary: {summary}"


def generate_embedding_by_paper_obj(paper_obj: object):
    text = generate_embedding_text(paper_obj)
    # return generate_embedding(text)
    return generate_embedding_http(text)


if __name__ == "__main__":
    paper_obj = {
        "title": "TKG-DM: Training-free Chroma Key Content Generation Diffusion Model",
        "keywords": ["chroma", "foreground", "background", "diffusion", "generation", "content"],
        "summary": "Diffusion models have enabled the generation of high-quality images..."
    }
    print(generate_embedding_by_paper_obj(paper_obj))
