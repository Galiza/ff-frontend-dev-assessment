from io import BytesIO
from pathlib import Path
from datastar_py.django import DatastarResponse
from datastar_py.sse import ServerSentEventGenerator as SSE
import json
from datastar_py.consts import ElementPatchMode
from django.http import FileResponse
from django.http import JsonResponse
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
            "redactions": redactions
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
        data = json.loads(request.body.decode("utf-8"))
        redaction_type = data.get("type")
        coordinates = data.get("coordinates")
        required_fields = {"x", "y", "width", "height", "page"}

        #JSON validation
        if redaction_type not in ("text", "area"):
            return JsonResponse({"error": "Invalid redaction type"}, status=400)
        if not isinstance(coordinates, dict):
            return JsonResponse({"error": "Invalid coordinates"}, status=400)
        if not required_fields.issubset(coordinates):
            return JsonResponse({"error": "Missing coordinate fields"}, status=400)
        
        # Convert coordinate values to float
        float_coords = {"page": coordinates.get("page")}
        for key in ("x", "y", "width", "height"):
            value = coordinates.get(key)
            try:
                float_coords[key] = float(value)
            except (TypeError, ValueError):
                return JsonResponse({"error": f"Invalid coordinate value for {key}"}, status=400)
            
        # Create the redaction
        redaction = Redaction.objects.create(document=document, redaction_type=redaction_type, coordinates=float_coords)

        # Get redaction size after creation
        redactions_len = len(document.redactions.all())
        
        redaction_list_item_html = render_to_string(
            "redaction/redaction_list_item.html",
            {"redaction": redaction, "document": document}
        )
        
        redaction_drawing_black_square = (
            f'<div id="redaction-{redaction.id}"'
            f'data-show="$coordinates.page === {redaction.coordinates["page"]}" '
            f'class="absolute '
            f'left-[calc({redaction.coordinates["x"]}px*var(--scale-factor))] '
            f'top-[calc({redaction.coordinates["y"]}px*var(--scale-factor))] '
            f'w-[calc({redaction.coordinates["width"]}px*var(--scale-factor)+1px)] '
            f'h-[calc({redaction.coordinates["height"]}px*var(--scale-factor))] '
            f'bg-black ' 
            f'z-10"></div>'
        )

        elements_to_patch = [
            SSE.patch_elements(f"<span id=\"redaction-count\" class=\"font-semibold\">{redactions_len}</span>"),
            SSE.patch_elements(redaction_list_item_html,
                               selector="#redactions-list",
                                mode=ElementPatchMode.APPEND),
            SSE.patch_elements(redaction_drawing_black_square,
                                selector="#annotation-layer",
                                mode=ElementPatchMode.APPEND)
        ]

        if redactions_len == 0:
            elements_to_patch.append(
                SSE.patch_elements(
                    "",
                    selector="#empty-redactions",
                    mode=ElementPatchMode.REMOVE
                )
            )

        return DatastarResponse(elements_to_patch)

    except Exception as e:
        import traceback
        print("[redaction_create] Exception:", e)
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["DELETE"])
def redaction_delete(request, document_id, redaction_id):
    """
    Delete a redaction for a document.
    Accepts DELETE requests with JSON or form data:
    {
        "document_id": 1,
        "redaction_id": 1
    }
    Returns JSON for frontend reactivity.
    """
    document = get_object_or_404(Document, pk=document_id)
    try:
        # Fetch redaction by document and redaction ID to delete
        redaction = Redaction.objects.get(document=document, pk=redaction_id)

        # Create selector for overlay and list item before deleting
        overlay_selector = f"#redaction-{redaction.id}"
        list_item_selector = f"#redaction-item-{redaction.id}"

        # Delete redaction
        redaction.delete()

        # Get redaction size after deletion
        redactions_len = len(document.redactions.all())

        elements_to_patch = [
            SSE.patch_elements(f"<span id=\"redaction-count\" class=\"font-semibold\">{redactions_len}</span>"),
            SSE.patch_elements(selector=overlay_selector, mode=ElementPatchMode.REMOVE),
            SSE.patch_elements(selector=list_item_selector, mode=ElementPatchMode.REMOVE)
        ]

        if redactions_len == 0:
            elements_to_patch.append(
                SSE.patch_elements(
                    render_to_string("redaction/empty_redaction_list.html"),
                    selector="#redactions-list",
                    mode=ElementPatchMode.APPEND
                )
            )

        return DatastarResponse(elements_to_patch)

    except Exception as e:
        import traceback
        print("[redaction_create] Exception:", e)
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=400)

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
