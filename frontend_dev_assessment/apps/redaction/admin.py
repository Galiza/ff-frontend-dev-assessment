from django.contrib import admin

from .models import Document
from .models import Redaction


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "uploaded_at"]
    search_fields = ["title"]
    readonly_fields = ["uploaded_at"]


@admin.register(Redaction)
class RedactionAdmin(admin.ModelAdmin):
    list_display = ["document", "redaction_type", "get_coordinates_display", "created_at"]
    list_filter = ["redaction_type", "created_at"]
    search_fields = ["document__title"]
    readonly_fields = ["created_at"]
