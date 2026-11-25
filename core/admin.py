from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from .models import Document, QuestionLog
from .services.documents import process_document
from .services.rag import retrieve_chunks, generate_answer
import time


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "updated_at", "indexed_status")
    search_fields = ("title", "content")
    readonly_fields = ("content_preview", "created_at", "updated_at", "indexed_at")
    fields = ("title", "file", "content_preview", "created_at", "updated_at", "indexed_at")

    @admin.display(description="Index status")
    def indexed_status(self, obj):
        if obj.is_indexed:
            return format_html('<span style="color:green;font-weight:bold">Indexed</span>')
        return format_html('<span style="color:#b45309;font-weight:bold">Not indexed</span>')

    @admin.display(description="Extracted text preview")
    def content_preview(self, obj):
        if not obj or not obj.pk:
            return "Save the document first."
        return (obj.content or "No text extracted yet.")[:1500]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            process_document(obj)
            self.message_user(request, "Document processed and indexed successfully.", messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Document saved, but indexing failed: {exc}", messages.ERROR)


@admin.register(QuestionLog)
class QuestionLogAdmin(admin.ModelAdmin):
    change_list_template = "admin/core/questionlog/change_list.html"
    list_display = ("question_short", "status", "processing_time_ms", "created_at")
    search_fields = ("question", "answer")
    readonly_fields = (
        "question", "answer", "sources", "created_at",
        "processing_time_ms", "status", "error_message"
    )
    fields = readonly_fields

    def get_urls(self):
        custom_urls = [
            path(
                "ask/",
                self.admin_site.admin_view(self.ask_view),
                name="core_questionlog_ask",
            ),
        ]
        return custom_urls + super().get_urls()

    def ask_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "title": "Ask your documents",
            "opts": self.model._meta,
            "documents": Document.objects.filter(indexed_at__isnull=False).order_by("title"),
            "result": None,
            "error": None,
        }

        if request.method == "POST":
            question = request.POST.get("question", "").strip()
            selected_ids = request.POST.getlist("document_ids")
            if not question:
                context["error"] = "Please enter a question."
            else:
                started = time.perf_counter()
                log = QuestionLog.objects.create(question=question, status="success")
                try:
                    ids = [int(value) for value in selected_ids] if selected_ids else None
                    docs = retrieve_chunks(question, document_ids=ids, top_k=5)
                    answer = generate_answer(question, docs)
                    sources = [
                        {
                            "document_id": int(doc.metadata.get("document_id")),
                            "title": doc.metadata.get("title", ""),
                            "chunk_index": doc.metadata.get("chunk_index"),
                            "excerpt": doc.page_content[:500],
                        }
                        for doc in docs
                    ]
                    elapsed = int((time.perf_counter() - started) * 1000)
                    log.answer = answer
                    log.sources = sources
                    log.processing_time_ms = elapsed
                    log.save(update_fields=["answer", "sources", "processing_time_ms"])
                    context["result"] = {
                        "question": question,
                        "answer": answer,
                        "sources": sources,
                        "processing_time_ms": elapsed,
                        "history_url": reverse("admin:core_questionlog_change", args=[log.pk]),
                    }
                except Exception as exc:
                    elapsed = int((time.perf_counter() - started) * 1000)
                    log.status = "failed"
                    log.error_message = str(exc)
                    log.processing_time_ms = elapsed
                    log.save(update_fields=["status", "error_message", "processing_time_ms"])
                    context["error"] = str(exc)

        context["selected_ids"] = request.POST.getlist("document_ids") if request.method == "POST" else []
        context["question_value"] = request.POST.get("question", "") if request.method == "POST" else ""
        return render(request, "admin/core/questionlog/ask.html", context)

    @admin.display(description="Question")
    def question_short(self, obj):
        return obj.question[:80]
