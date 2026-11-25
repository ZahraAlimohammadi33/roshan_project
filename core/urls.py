from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, ask_question, history_list, history_detail

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("", include(router.urls)),
    path("ask/", ask_question, name="ask"),
    path("history/", history_list, name="history-list"),
    path("history/<int:pk>/", history_detail, name="history-detail"),
]
