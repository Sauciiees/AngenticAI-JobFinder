import os
from chromadb import PersistentClient
from langchain_google_genai import GoogleGenerativeAIEmbeddings


class JobVectorStore:

  def __init__(self, persist_directory="./vector_db"):
    # Initialize persistent ChromaDB client
    self.client = PersistentClient(path=persist_directory)
    self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")

    # Get or create a collection for job semantic search
    self.collection = self.client.get_or_create_collection(
        name="job_finder_semantic_search"
    )

  def add_documents(self, documents: list[str], metadatas: list[dict], ids: list[str]):
    """Embed and store text chunks (e.g., job descriptions or resume sections)."""
    vectors = self.embeddings.embed_documents(documents)
    self.collection.upsert(
        documents=documents, embeddings=vectors, metadatas=metadatas, ids=ids
    )

  def semantic_search(self, query: str, n_results: int = 3):
    """Search the vector database for text most semantically similar to the query."""
    query_vector = self.embeddings.embed_query(query)
    results = self.collection.query(
        query_embeddings=[query_vector], n_results=n_results
    )
    return results


# Example singleton or instantiation helper
vector_store = JobVectorStore()

def index_and_search_jobs(raw_jobs: list[dict], user_skills_query: str):
  docs = []
  metadatas = []
  ids = []

  for i, job in enumerate(raw_jobs):
    doc_text = f"{job.get('title', '')} - {job.get('snippet', '')}"
    docs.append(doc_text)
    metadatas.append({"link": job.get("link", "")})
    ids.append(f"job_{i}")

  # Store into vector DB
  vector_store.add_documents(docs, metadatas, ids)

  # Perform semantic search for top matches
  search_results = vector_store.semantic_search(
      query=user_skills_query, n_results=3
  )
  return search_results