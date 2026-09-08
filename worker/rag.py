import os
import re
from pathlib import Path

import chromadb
from pypdf import PdfReader


DOCUMENTS_DIR = Path("/documents")
COLLECTION_NAME = "relay_internal_documents"


def get_chroma_client():
    return chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST", "chromadb"),
        port=int(os.getenv("CHROMA_PORT", "8000")),
    )


def get_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
    )


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(
    text: str,
    chunk_size: int = 120,
    overlap: int = 25,
) -> list[str]:
    words = text.split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size

        chunk = " ".join(words[start:end])

        chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap

    return chunks


def index_documents():
    collection = get_collection()

    total_chunks = 0

    for pdf_path in sorted(DOCUMENTS_DIR.glob("*.pdf")):
        reader = PdfReader(pdf_path)

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            text = clean_text(
                page.extract_text() or ""
            )

            chunks = chunk_text(text)

            for chunk_index, chunk in enumerate(chunks):
                document_id = (
                    f"{pdf_path.stem}"
                    f"-p{page_number}"
                    f"-c{chunk_index}"
                )

                collection.upsert(
                    ids=[document_id],
                    documents=[chunk],
                    metadatas=[
                        {
                            "source_type": "internal_document",
                            "source": pdf_path.name,
                            "page": page_number,
                            "chunk_index": chunk_index,
                        }
                    ],
                )

                total_chunks += 1

    return total_chunks


def search_internal_documents(
    query: str,
    n_results: int = 3,
) -> list[dict]:
    collection = get_collection()

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    matches = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        matches.append(
            {
                "content": document,
                "source": metadata["source"],
                "source_type": metadata["source_type"],
                "page": metadata["page"],
                "distance": distance,
            }
        )

    return matches
