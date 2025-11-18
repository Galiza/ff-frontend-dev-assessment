from django.urls import path

from . import views

app_name = "redaction"

urlpatterns = [
    # Document views
    path("", views.document_list, name="document_list"),
    path("document/<int:pk>/", views.document_detail, name="document_detail"),
    # Redaction API endpoints
    path("document/<int:document_id>/redactions/create/", views.redaction_create, name="redaction_create"),
    path("document/<int:document_id>/redaction/<int:redaction_id>/delete/", views.redaction_delete, name="redaction_delete"),
    # Download redacted PDF
    path("document/<int:document_id>/download/", views.document_download_redacted, name="document_download"),
]
