from django.test import TestCase
from rest_framework.test import APIClient
from .models import Document, QuestionLog

class BasicApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_document_list_endpoint(self):
        response = self.client.get("/api/documents/")
        self.assertEqual(response.status_code, 200)

    def test_history_endpoint(self):
        QuestionLog.objects.create(question="What is RAG?", answer="...")
        response = self.client.get("/api/history/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
