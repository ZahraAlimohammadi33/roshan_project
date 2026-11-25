import os
from functools import lru_cache
from django.conf import settings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

@lru_cache(maxsize=1)
def get_vector_store():
    return Chroma(
        collection_name="document_qa",
        persist_directory=settings.CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
    )

def delete_document_vectors(document_id):
    store = get_vector_store()
    store.delete(where={"document_id": str(document_id)})

def retrieve_chunks(question, document_ids=None, top_k=5):
    store = get_vector_store()
    search_filter = None
    if document_ids:
        ids = [str(item) for item in document_ids]
        search_filter = {"document_id": {"$in": ids}}
    # MMR balances relevance and diversity so the context is less repetitive.
    return store.max_marginal_relevance_search(
        question,
        k=top_k,
        fetch_k=max(top_k * 4, 20),
        lambda_mult=0.7,
        filter=search_filter,
    )

def generate_answer(question, retrieved_docs):
    if not retrieved_docs:
        return (
            "در اسناد بارگذاری‌شده اطلاعات مرتبطی برای پاسخ به این پرسش پیدا نکردم. "
            "لطفاً سند مرتبطی اضافه کنید یا پرسش را دقیق‌تر مطرح کنید."
        )

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured. Add your Groq API key to the .env file.")

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        temperature=0.1,
        max_retries=2,
    )

    context_parts = []
    for index, doc in enumerate(retrieved_docs, start=1):
        title = doc.metadata.get("title", "Unknown document")
        context_parts.append(f"[Source {index}: {title}]\\n{doc.page_content}")
    context = "\\n\\n---\\n\\n".join(context_parts)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a careful document question-answering assistant. "
         "Answer the user only using the supplied context. "
         "If the context does not contain enough information, clearly say so. "
         "Do not invent facts or use outside knowledge. "
         "Respond in the same language as the user's question. "
         "When useful, mention the source title in your answer."),
        ("human", "Context:\\n{context}\\n\\nQuestion:\\n{question}")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": context, "question": question})
