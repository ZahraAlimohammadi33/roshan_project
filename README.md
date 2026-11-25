# Document QA — RAG with Django, LangChain and Groq

A document question-answering system built for the supplied LLM internship assignment. It supports DOCX upload, text extraction, chunking, multilingual vector embeddings, Chroma retrieval, Groq-based answer generation, Django Admin, REST API and question history.

## Architecture

1. A DOCX file is uploaded through Django Admin or the REST API.
2. `python-docx` extracts paragraphs and table cells into the `Document.content` field.
3. LangChain's `RecursiveCharacterTextSplitter` splits the text into overlapping chunks.
4. `HuggingFaceEmbeddings` creates multilingual embeddings locally.
5. ChromaDB stores chunks and metadata persistently.
6. A question is embedded and relevant chunks are retrieved from Chroma.
7. A LangChain prompt + Groq chat model generates an answer using only retrieved context.
8. The question, answer, processing time and source excerpts are saved in `QuestionLog`.

## Requirements

- Docker Desktop / Docker Engine and Docker Compose
- A Groq API key: https://console.groq.com/keys
- A chat model enabled for your Groq account. The default is `openai/gpt-oss-20b`.

The app uses Groq's OpenAI-compatible Chat Completions endpoint (`https://api.groq.com/openai/v1`) through the existing `langchain-openai` integration. No additional Groq SDK or dependency is required. Check Groq's current model catalog and account rate limits before changing `GROQ_MODEL`:
- Models: https://console.groq.com/docs/models
- Rate limits: https://console.groq.com/docs/rate-limits

The embedding model is downloaded from Hugging Face on the first run. The first startup can take several minutes and requires internet access. Later runs reuse the cached model inside the container only if the image/container cache remains available; for durable caching, add a mounted Hugging Face cache volume.

## Quick start with Docker

```bash
cp .env.example .env
```

Edit `.env` and set `GROQ_API_KEY` and, if needed, `GROQ_MODEL`. Then run:

```bash
docker compose up --build
```

Open:
- Admin: http://localhost:8000/admin/
- API root: http://localhost:8000/api/

Create an administrator in another terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

Stop:

```bash
docker compose down
```

Data is stored in named Docker volumes (`sqlite_data`, `chroma_data`, `media_data`). To delete all data, including uploaded files and vector index:

```bash
docker compose down -v
```

## Local development (without Docker)

Python 3.11 is recommended.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows CMD
# cp .env.example .env   # macOS/Linux
```

Set `GROQ_API_KEY` in `.env`, then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Admin usage

1. Sign in at `/admin/`.
2. Open **Documents** and add a title plus a `.docx` file.
3. Save. The app extracts the text and indexes its chunks.
4. Open **Question logs** and click **Ask your documents** to ask questions directly inside Django Admin. Answers show retrieved source excerpts and are saved automatically. The Question logs list lets you inspect previous questions, answers and failures.

Editing a document reprocesses and replaces its vector chunks. Deleting a document removes its vectors through a Django signal.

## REST API

All endpoints are under `/api/`. The API is intentionally simple for evaluation. In a production deployment, add authentication, permissions, rate limiting and request quotas.

### 1. List documents

`GET /api/documents/`

### 2. Upload a DOCX

`POST /api/documents/` — `multipart/form-data`

Fields:
- `title`: document title
- `file`: `.docx` file

Example:

```bash
curl -X POST http://localhost:8000/api/documents/ \\
  -F "title=Company Handbook" \\
  -F "file=@sample_data/company_handbook.docx"
```

### 3. Retrieve, edit or delete a document

- `GET /api/documents/{id}/`
- `PATCH /api/documents/{id}/` — send `title` and/or a replacement `file`
- `DELETE /api/documents/{id}/`

### 4. Reindex a document

`POST /api/documents/{id}/reindex/`

Useful after changing the embedding model or recovering a vector index.

### 5. Ask a question

`POST /api/ask/` — JSON

```json
{
  "question": "What is the annual leave policy?",
  "document_ids": [1],
  "top_k": 5
}
```

`document_ids` is optional. If omitted, search runs across all indexed documents. `top_k` is optional (default 5, maximum 15).

Example response:

```json
{
  "id": 1,
  "question": "What is the annual leave policy?",
  "answer": "The document states ...",
  "sources": [
    {
      "document_id": 1,
      "title": "Company Handbook",
      "chunk_index": 2,
      "excerpt": "..."
    }
  ],
  "processing_time_ms": 1840
}
```

### 6. Question history

- `GET /api/history/` — latest 100 entries
- `GET /api/history/{id}/` — one entry

### Error behavior

- Invalid file extension or missing fields: `400`
- Unknown document ID: `400`
- Missing/invalid Groq key, provider failure or retrieval failure: `502`; a failed history record is still saved.
- No relevant chunks: a clear no-information answer is returned and saved, without calling the LLM.

## Sample data

`sample_data/company_handbook.docx` is a small synthetic English-language document for smoke testing. Upload it, then ask questions whose answers are explicitly present in it.

## Important engineering notes and limitations

- This is a synchronous prototype suitable for a small internship assignment. For large files or many concurrent users, move document processing and question answering to a background queue such as Celery.
- The vector index is separate from the relational database. If the Chroma volume is deleted, reindex documents through the admin/API.
- The current retrieval is semantic vector search. A production version could add BM25 keyword retrieval, hybrid fusion, reranking, page-level citations and access-control filters.
- The API currently allows unauthenticated access for easy local evaluation. Do not expose it publicly without authentication and authorization.
- DOCX paragraph and table text are extracted. Images, charts, comments, headers/footers and complex layouts are not OCR-processed.
- The prompt asks the model to use only retrieved context, but an LLM can still make mistakes. Evaluate with a test set and inspect sources.

## Basic test

```bash
python manage.py test
```
