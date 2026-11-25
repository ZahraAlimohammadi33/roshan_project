from pathlib import Path
from rest_framework import serializers
from .models import Document, QuestionLog
from .services.documents import process_document

class DocumentSerializer(serializers.ModelSerializer):
    is_indexed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Document
        fields = ["id", "title", "file", "content", "created_at", "updated_at", "indexed_at", "is_indexed"]
        read_only_fields = ["content", "created_at", "updated_at", "indexed_at"]

    def validate_file(self, value):
        if Path(value.name).suffix.lower() != ".docx":
            raise serializers.ValidationError("Only .docx files are supported.")
        return value

    def create(self, validated_data):
        instance = super().create(validated_data)
        process_document(instance)
        instance.refresh_from_db()
        return instance

    def update(self, instance, validated_data):
        old_file_name = instance.file.name
        should_reindex = (
            "file" in validated_data
            or "title" in validated_data
            or not instance.is_indexed
        )
        instance = super().update(instance, validated_data)
        if should_reindex:
            process_document(instance)
        if old_file_name and old_file_name != instance.file.name:
            try:
                instance.file.storage.delete(old_file_name)
            except Exception:
                pass
        instance.refresh_from_db()
        return instance

class QuestionRequestSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=5000)
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=False
    )
    top_k = serializers.IntegerField(min_value=1, max_value=15, required=False)

class QuestionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionLog
        fields = ["id", "question", "answer", "sources", "created_at", "processing_time_ms", "status", "error_message"]
