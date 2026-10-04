import os
from agent.vector_store import vector_store
from pypdf import PdfReader


def parse_and_store_document(file_path: str, user_id: str, doc_type: str = "resume"):
  """Reads a PDF, extracts text, and stores it in ChromaDB tagged by user_id."""
  if not os.path.exists(file_path):
    raise FileNotFoundError(f"File not found: {file_path}")

  reader = PdfReader(file_path)
  extracted_text = ""

  for page_num, page in enumerate(reader.pages):
    text = page.extract_text()
    if text:
      extracted_text += f"\n--- Page {page_num + 1} ---\n{text}"

  chunks = [
      chunk.strip()
      for chunk in extracted_text.split("\n\n")
      if len(chunk.strip()) > 20
  ]

  if not chunks:
    chunks = [extracted_text]

  # INJECT USER ID HERE: Tag every chunk with the specific user_id
  metadatas = [
      {"source_file": os.path.basename(file_path), "type": doc_type, "user_id": user_id} 
      for _ in chunks
  ]
  ids = [f"{user_id}_{doc_type}_{i}" for i in range(len(chunks))]

  vector_store.add_documents(documents=chunks, metadatas=metadatas, ids=ids)

  print(f"Successfully parsed {len(chunks)} chunks for User: {user_id}!")
  return chunks