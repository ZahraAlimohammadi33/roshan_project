import time
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import Document, QuestionLog
from .serializers import DocumentSerializer, QuestionRequestSerializer, QuestionLogSerializer
from .services.rag import retrieve_chunks, generate_answer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    @action(detail=True, methods=["post"], url_path="reindex")
    def reindex(self, request, pk=None):
        from .services.documents import process_document
        document = self.get_object()
        try:
            count = process_document(document)
            document.refresh_from_db()
            return Response({
                "message": "Document indexed successfully.",
                "document_id": document.id,
                "chunks": count,
                "indexed_at": document.indexed_at,
            })
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def ask_question(request):
    serializer = QuestionRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    question = data["question"].strip()
    if not question:
        raise ValidationError({"question": "Question cannot be empty."})

    document_ids = data.get("document_ids")
    top_k = data.get("top_k", 5)

    if document_ids:
        existing_ids = set(Document.objects.filter(id__in=document_ids).values_list("id", flat=True))
        missing = sorted(set(document_ids) - existing_ids)
        if missing:
            raise ValidationError({"document_ids": f"Unknown document IDs: {missing}"})

    started = time.perf_counter()
    log = QuestionLog.objects.create(question=question, status="success")
    try:
        docs = retrieve_chunks(question, document_ids=document_ids, top_k=top_k)
        answer = generate_answer(question, docs)
        sources = []
        for doc in docs:
            sources.append({
                "document_id": int(doc.metadata.get("document_id")),
                "title": doc.metadata.get("title", ""),
                "chunk_index": doc.metadata.get("chunk_index"),
                "excerpt": doc.page_content[:500],
            })
        elapsed = int((time.perf_counter() - started) * 1000)
        log.answer = answer
        log.sources = sources
        log.processing_time_ms = elapsed
        log.save(update_fields=["answer", "sources", "processing_time_ms"])
        return Response({
            "id": log.id,
            "question": question,
            "answer": answer,
            "sources": sources,
            "processing_time_ms": elapsed,
        })
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        log.status = "failed"
        log.error_message = str(exc)
        log.processing_time_ms = elapsed
        log.save(update_fields=["status", "error_message", "processing_time_ms"])
        return Response(
            {"error": "Question processing failed.", "detail": str(exc), "history_id": log.id},
            status=status.HTTP_502_BAD_GATEWAY,
        )

@api_view(["GET"])
def history_list(request):
    logs = QuestionLog.objects.all()[:100]
    return Response(QuestionLogSerializer(logs, many=True).data)

@api_view(["GET"])
def history_detail(request, pk):
    try:
        log = QuestionLog.objects.get(pk=pk)
    except QuestionLog.DoesNotExist:
        return Response({"error": "History item not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(QuestionLogSerializer(log).data)
