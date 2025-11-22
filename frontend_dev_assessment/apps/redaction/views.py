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
    REDACTIONS_LIST_SELECTOR = "#redactions-list"
    ANNOTATION_LAYER_SELECTOR = "#annotation-layer"
    EMPTY_REDACTIONS_SELECTOR = "#empty-redactions"

    try:
        data = json.loads(request.body.decode("utf-8"))
        redaction_type = data.get("type")
        coordinates = data.get("coordinates")
        required_fields = {"x", "y", "width", "height"}
        selections = coordinates.get("selections") if isinstance(coordinates, dict) and redaction_type == "text" else None
        
        if selections and len(selections) > 1:
            # Create ONE redaction with multiple coordinate boxes
            float_coords = {
                "page": coordinates.get("page"),
                "boxes": []  # Array of boxes
            }
            
            for sel in selections:
                if not required_fields.issubset(sel):
                    continue
                    
                float_coords["boxes"].append({
                    "x": float(sel["x"]),
                    "y": float(sel["y"]),
                    "width": float(sel["width"]),
                    "height": float(sel["height"])
                })
            
            # Create single redaction with multiple boxes
            redaction = Redaction.objects.create(
                document=document, 
                redaction_type=redaction_type, 
                coordinates=float_coords
            )
            
            # Build response
            redactions_len = document.redactions.count()
            
            redaction_list_item_html = render_to_string(
                "redaction/redaction_list_item.html",
                {"redaction": redaction, "document": document}
            )
            
            # Create multiple divs but all with the same redaction ID
            redaction_boxes_html = ""
            for i, box in enumerate(float_coords["boxes"]):
                redaction_boxes_html += (
                    f'<div id="redaction-{redaction.id}-box-{i}" '
                    f'data-redaction-id="{redaction.id}" '
                    f'data-show="$coordinates.page === {float_coords["page"]}" '
                    f'class="select-none absolute '
                    f'left-[calc({box["x"]}px*var(--scale-factor))] '
                    f'top-[calc({box["y"]}px*var(--scale-factor))] '
                    f'w-[calc({box["width"]}px*var(--scale-factor))] '
                    f'h-[calc({box["height"]}px*var(--scale-factor))] '
                    f'bg-black z-20"></div>'
                )
            
            elements_to_patch = [
                SSE.patch_elements(f'<span id="redaction-count" class="font-semibold">{redactions_len}</span>'),
                SSE.patch_elements(
                    redaction_list_item_html,
                    selector=REDACTIONS_LIST_SELECTOR,
                    mode=ElementPatchMode.APPEND
                ),
                SSE.patch_elements(
                    redaction_boxes_html,
                    selector=ANNOTATION_LAYER_SELECTOR,
                    mode=ElementPatchMode.APPEND
                )
            ]
            
            if redactions_len > 0:
                elements_to_patch.append(
                    SSE.patch_elements(
                        "",
                        selector=EMPTY_REDACTIONS_SELECTOR,
                        mode=ElementPatchMode.REMOVE
                    )
                )
            
            return DatastarResponse(elements_to_patch)
        
        else:
            # Single selection or area mode - handle normally
            if selections and len(selections) == 1:
                # Single text selection
                sel = selections[0]
                float_coords = {
                    "page": coordinates.get("page"),
                    "x": float(sel["x"]),
                    "y": float(sel["y"]),
                    "width": float(sel["width"]),
                    "height": float(sel["height"])
                }
            else:                
                if redaction_type not in ("text", "area"):
                    return JsonResponse({"error": "Invalid redaction type"}, status=400)
                if not isinstance(coordinates, dict):
                    return JsonResponse({"error": "Invalid coordinates"}, status=400)
                if not required_fields.issubset(coordinates):
                    return JsonResponse({"error": "Missing coordinate fields"}, status=400)
                
                float_coords = {"page": coordinates.get("page")}
                for key in ("x", "y", "width", "height"):
                    value = coordinates.get(key)
                    try:
                        float_coords[key] = float(value)
                    except (TypeError, ValueError):
                        return JsonResponse({"error": f"Invalid coordinate value for {key}"}, status=400)
            
            redaction = Redaction.objects.create(
                document=document, 
                redaction_type=redaction_type, 
                coordinates=float_coords
            )

            redactions_len = document.redactions.count()
            
            redaction_list_item_html = render_to_string(
                "redaction/redaction_list_item.html",
                {"redaction": redaction, "document": document}
            )
            
            redaction_drawing_black_square = (
                f'<div id="redaction-{redaction.id}" '
                f'data-redaction-id="{redaction.id}" '
                f'data-show="$coordinates.page === {redaction.coordinates["page"]}" '
                f'class="select-none absolute '
                f'left-[calc({redaction.coordinates["x"]}px*var(--scale-factor))] '
                f'top-[calc({redaction.coordinates["y"]}px*var(--scale-factor))] '
                f'w-[calc({redaction.coordinates["width"]}px*var(--scale-factor))] '
                f'h-[calc({redaction.coordinates["height"]}px*var(--scale-factor))] '
                f'bg-black z-20"></div>'
            )

            elements_to_patch = [
                SSE.patch_elements(f'<span id="redaction-count" class="font-semibold">{redactions_len}</span>'),
                SSE.patch_elements(
                    redaction_list_item_html,
                    selector=REDACTIONS_LIST_SELECTOR,
                    mode=ElementPatchMode.APPEND
                ),
                SSE.patch_elements(
                    redaction_drawing_black_square,
                    selector=ANNOTATION_LAYER_SELECTOR,
                    mode=ElementPatchMode.APPEND
                )
            ]

            if redactions_len > 0:
                elements_to_patch.append(
                    SSE.patch_elements(
                        "",
                        selector=EMPTY_REDACTIONS_SELECTOR,
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
        redaction = Redaction.objects.get(document=document, pk=redaction_id)

        # Build selectors for all boxes associated with this redaction
        selectors_to_remove = [f"#redaction-item-{redaction.id}"]
        
        # Check if this is a multi-box redaction
        if "boxes" in redaction.coordinates and redaction.coordinates["boxes"]:
            # Remove all boxes
            for i in range(len(redaction.coordinates["boxes"])):
                selectors_to_remove.append(f"#redaction-{redaction.id}-box-{i}")
        else:
            # Single box
            selectors_to_remove.append(f"#redaction-{redaction.id}")

        # Delete redaction
        redaction.delete()

        redactions_len = document.redactions.count()

        elements_to_patch = [
            SSE.patch_elements(f'<span id="redaction-count" class="font-semibold">{redactions_len}</span>')
        ]
        
        # Remove all related elements
        for selector in selectors_to_remove:
            elements_to_patch.append(
                SSE.patch_elements(selector=selector, mode=ElementPatchMode.REMOVE)
            )

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
        print("[redaction_delete] Exception:", e)
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

                # Check if this is a multi-box redaction
                from pypdf.generic import ArrayObject
                from pypdf.generic import DictionaryObject
                from pypdf.generic import FloatObject
                from pypdf.generic import NameObject

                def add_redaction_annotation(x, y, width, height):
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

                if "boxes" in coords and coords["boxes"]:
                    for box in coords["boxes"]:
                        x, y, width, height = extract_pdf_coords(box, page_height)
                        add_redaction_annotation(x, y, width, height)
                else:
                    x, y, width, height = extract_pdf_coords(coords, page_height)
                    add_redaction_annotation(x, y, width, height)

            writer.add_page(page)

        # Create in-memory file
        output = BytesIO()
        writer.write(output)
        output.seek(0)

        # Return as file download
        return FileResponse(
            output, content_type="application/pdf", as_attachment=True, filename=f"{document.title}_redacted.pdf"
        )

def extract_pdf_coords(box, page_height):
    x = float(box.get("x", 0))
    y = page_height - float(box.get("y", 0)) - float(box.get("height", 0))
    width = float(box.get("width", 0))
    height = float(box.get("height", 0))
    return x, y, width, height