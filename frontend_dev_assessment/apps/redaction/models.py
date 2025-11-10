from django.db import models


class Document(models.Model):
    """
    Model to store PDF documents for redaction.
    """

    title = models.CharField(max_length=255, help_text="Document title")
    file = models.FileField(upload_to="documents/", help_text="PDF file")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title


class Redaction(models.Model):
    """
    Model to store redaction areas/selections for a document.
    Each redaction stores coordinates and page information.
    """

    REDACTION_TYPE_CHOICES = [
        ("text", "Text Selection"),
        ("area", "Area Drawing"),
    ]

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="redactions", help_text="Associated document"
    )
    redaction_type = models.CharField(
        max_length=10, choices=REDACTION_TYPE_CHOICES, help_text="Type of redaction (text selection or area drawing)"
    )
    coordinates = models.JSONField(help_text="Redaction coordinates in format: {x, y, width, height, page}")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "created_at"]

    def __str__(self):
        return (
            f"{self.get_redaction_type_display()} on {self.document.title} (Page {self.coordinates.get('page', 'N/A')})"
        )

    def get_coordinates_display(self):
        """Helper method to display coordinates nicely"""
        coords = self.coordinates
        return f"Page {coords.get('page', '?')}: ({coords.get('x', 0)}, {coords.get('y', 0)}) - {coords.get('width', 0)}x{coords.get('height', 0)}"  # noqa: E501
