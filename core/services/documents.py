from pathlib import Path
import os
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from django.utils import timezone
from .rag import get_vector_store, delete_document_vectors
from ..models import Document

def extract_docx_text(file_path: str) -> str:
    """Extract paragraph and table text from a DOCX file."""
    doc = DocxDocument(file_path)
    parts = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\\n", " ") for cell in row.cells]
            row_text = " | ".join(cell for cell in cells if cell)
            if row_text:
                parts.append(row_text)

    return "\\n".join(parts).strip()

def process_document(document: Document) -> int:
    """Extract, chunk, embed, and index one document. Returns chunk count."""
    if not document.file:
        raise ValueError("No DOCX file has been uploaded.")

    suffix = Path(document.file.name).suffix.lower()
    if suffix != ".docx":
        raise ValueError("Only .docx files are supported.")

    text = extract_docx_text(document.file.path)
    if not text:
        raise ValueError("No readable text was found in this DOCX file.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=int(os.getenv("CHUNK_SIZE", "900")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "150")),
        separators=["\\n\\n", "\\n", "۔", ".", "!", "?", " ", ""],
    )
    chunks = splitter.split_text(text)
    if not chunks:
        raise ValueError("The document did not produce any text chunks.")

    # Replace old chunks only after extraction and splitting succeed.
    delete_document_vectors(document.pk)
    vector_store = get_vector_store()
    ids = [f"doc-{document.pk}-chunk-{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": str(document.pk), "title": document.title, "chunk_index": i}
        for i in range(len(chunks))
    ]
    vector_store.add_texts(texts=chunks, metadatas=metadatas, ids=ids)

    document.content = text
    document.indexed_at = timezone.now()
    document.save(update_fields=["content", "indexed_at", "updated_at"])
    return len(chunks)
