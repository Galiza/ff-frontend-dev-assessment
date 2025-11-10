from io import BytesIO
from pathlib import Path

from datastar_py.django import datastar_response
from datastar_py.sse import ServerSentEventGenerator as SSE
from django.http import FileResponse
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pypdf import PdfReader
from pypdf import PdfWriter

from .models import Document
from .models import Redaction


def document_list(request):
    """
    Display list of all available documents.
    These are pre-seeded in the database.
    """
    documents = Document.objects.all()
    return render(request, "redaction/document_list.html", {"documents": documents})


def document_detail(request, pk):
    """
    Display a specific document with PDF viewer interface.
    This is where candidates will implement the PDF.js viewer and redaction UI.
    """
    document = get_object_or_404(Document, pk=pk)
    redactions = document.redactions.all()

    return render(
        request,
        "redaction/document_detail.html",
        {
            "document": document,
            "redactions": redactions,
        },
    )


@csrf_exempt  # You do not have to worry about CSRF tokens in this assessment
@require_http_methods(["POST"])
def redaction_create(request, document_id):  # noqa: ARG001
    """
    Create a new redaction for a document.

    TODO for candidates: This is a flexible endpoint that accepts redaction data.
    Candidates can implement this in different ways:
    - Accept JSON data directly
    - Use form data
    - Return JSON response or HTML fragment for DataStar

    Expected data format (example):
    {
        "type": "text" or "area",
        "coordinates": {
            "x": 100,
            "y": 200,
            "width": 150,
            "height": 20,
            "page": 1
        }
    }

    The candidate should:
    1. Parse the incoming request data
    2. Validate the coordinates
    3. Create the Redaction object
    4. Return appropriate response (JSON or HTML fragment)
    """
    document = get_object_or_404(Document, pk=document_id)

    try:
        # TODO: Implement request parsing based on your frontend approach

        redaction_type = None
        coordinates = None

        # Create the redaction
        redaction = Redaction.objects.create(document=document, redaction_type=redaction_type, coordinates=coordinates)   # noqa: F841

        # TODO: Return appropriate response

    except Exception as e:
        raise HttpResponseBadRequest() from e


def document_download_redacted(request, document_id):  # noqa: ARG001
    """
    Generate and download a PDF with all redactions applied.
    This uses pypdf to black out the specified regions.
    """
    document = get_object_or_404(Document, pk=document_id)
    redactions = document.redactions.all()

    # Open the original PDF
    with Path(document.file.path).open("rb") as f:
        reader = PdfReader(f)
        writer = PdfWriter()

        # Process each page
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]

            # Get redactions for this page (page numbers are 1-indexed in our model)
            page_redactions = redactions.filter(coordinates__page=page_num + 1)

            # Apply redactions by drawing black rectangles
            for redaction in page_redactions:
                coords = redaction.coordinates

                # Get page dimensions
                page_height = float(page.mediabox.height)

                # Convert coordinates (PDF uses bottom-left origin)
                # Our frontend will use top-left origin, so we need to convert
                x = float(coords.get("x", 0))
                y = page_height - float(coords.get("y", 0)) - float(coords.get("height", 0))
                width = float(coords.get("width", 0))
                height = float(coords.get("height", 0))

                # Create a black rectangle annotation
                # Note: This is a simplified approach. pypdf can add redaction annotations
                from pypdf.generic import ArrayObject
                from pypdf.generic import DictionaryObject
                from pypdf.generic import FloatObject
                from pypdf.generic import NameObject

                redaction_annotation = DictionaryObject()
                redaction_annotation.update(
                    {
                        NameObject("/Type"): NameObject("/Annot"),
                        NameObject("/Subtype"): NameObject("/Square"),
                        NameObject("/Rect"): ArrayObject(
                            [FloatObject(x), FloatObject(y), FloatObject(x + width), FloatObject(y + height)]
                        ),
                        NameObject("/C"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),  # Black color
                        NameObject("/IC"): ArrayObject(
                            [FloatObject(0), FloatObject(0), FloatObject(0)]
                        ),  # Black interior
                        NameObject("/BS"): DictionaryObject(
                            {
                                NameObject("/W"): FloatObject(0),  # No border
                            }
                        ),
                    }
                )

                if "/Annots" not in page:
                    page[NameObject("/Annots")] = ArrayObject()
                page["/Annots"].append(redaction_annotation)

            writer.add_page(page)

        # Create in-memory file
        output = BytesIO()
        writer.write(output)
        output.seek(0)

        # Return as file download
        return FileResponse(
            output, content_type="application/pdf", as_attachment=True, filename=f"{document.title}_redacted.pdf"
        )
