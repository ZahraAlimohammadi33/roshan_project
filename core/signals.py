from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Document
from .services.rag import delete_document_vectors

@receiver(post_delete, sender=Document)
def remove_document_vectors(sender, instance, **kwargs):
    try:
        delete_document_vectors(instance.pk)
    except Exception:
        # Database deletion should not fail because the vector store is unavailable.
        pass
