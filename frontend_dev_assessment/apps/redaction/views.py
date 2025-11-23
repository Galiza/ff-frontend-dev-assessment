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
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject

from .models import Document, Redaction


# ============================================================================
# CONSTANTS
# ============================================================================

REDACTIONS_LIST_SELECTOR = "#redactions-list"
ANNOTATION_LAYER_SELECTOR = "#annotation-layer"
EMPTY_REDACTIONS_SELECTOR = "#empty-redactions"
REDACTION_COUNT_SELECTOR = "#redaction-count"
NOTIFICATION_SELECTOR = "#notification-container"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def validate_coordinates(coordinates, required_fields={"x", "y", "width", "height"}):
    """
    Validate that coordinates dictionary contains all required fields.
    
    Args:
        coordinates (dict): Coordinate data to validate
        required_fields (set): Set of required field names
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(coordinates, dict):
        return False, "Invalid coordinates format"
    
    if not required_fields.issubset(coordinates.keys()):
        missing = required_fields - coordinates.keys()
        return False, f"Missing coordinate fields: {missing}"
    
    return True, None


def convert_to_float_coords(coordinates, page=None):
    """
    Convert coordinate values from strings/numbers to floats.
    
    Args:
        coordinates (dict): Raw coordinate data
        page (int, optional): Page number to include
        
    Returns:
        dict: Coordinates with float values
        
    Raises:
        ValueError: If coordinate values cannot be converted to float
    """
    float_coords = {}
    
    if page is not None:
        float_coords["page"] = page
    
    for key in ("x", "y", "width", "height"):
        value = coordinates.get(key)
        try:
            float_coords[key] = float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid coordinate value for {key}: {value}") from e
    
    return float_coords


def extract_pdf_coords(coords, page_height):
    """
    Convert web coordinates to PDF coordinates.
    
    PDF coordinate system has origin at bottom-left, while web has top-left.
    This function performs the necessary transformation.
    
    Args:
        coords (dict): Coordinate dictionary with x, y, width, height
        page_height (float): Height of the PDF page
        
    Returns:
        tuple: (x, y, width, height) in PDF coordinate system
    """
    x = float(coords.get("x", 0))
    y = page_height - float(coords.get("y", 0)) - float(coords.get("height", 0))
    width = float(coords.get("width", 0))
    height = float(coords.get("height", 0))
    return x, y, width, height


def create_redaction_box_html(redaction_id, coordinates, page, redaction_type, is_multi_box=False, box_index=0):
    """
    Generate HTML for a redaction overlay element.
    
    Args:
        redaction_id (int): Database ID of the redaction
        coordinates (dict): Box coordinates (x, y, width, height)
        page (int): Page number where redaction appears
        is_multi_box (bool): Whether this is part of a multi-box redaction
        box_index (int): Index of box within multi-box redaction
        
    Returns:
        str: HTML string for the redaction overlay div
    """
    element_id = f"redaction-{redaction_id}"
    if is_multi_box:
        element_id += f"-box-{box_index}"
    
    color_class = "ring-blue-500" if redaction_type == "text" else "ring-purple-500"
    return (
        f'<div id="{element_id}" '
        f'data-redaction-id="{redaction_id}" '
        f'data-show="$coordinates.page === {page}" '
        f'data-on:mouseenter="$_hoveredRedaction = {redaction_id}" '
        f'data-on:mouseleave="$_hoveredRedaction = \'\'" '
        f'data-class="{{\'ring-4 {color_class} ring-opacity-70 z-30\': $_hoveredRedaction === {redaction_id}, \'z-20\': $_hoveredRedaction !== {redaction_id}}}" '
        f'class="pointer-events-auto select-none absolute '
        f'left-[calc({coordinates["x"]}px*var(--scale-factor))] '
        f'top-[calc({coordinates["y"]}px*var(--scale-factor))] '
        f'w-[calc({coordinates["width"]}px*var(--scale-factor))] '
        f'h-[calc({coordinates["height"]}px*var(--scale-factor))] '
        f'bg-black z-20"></div>'
    )


def build_redaction_response(document, redaction, is_multi_box=False):
    """
    Build DataStar response for redaction creation.
    
    Args:
        document (Document): Document model instance
        redaction (Redaction): Newly created redaction instance
        is_multi_box (bool): Whether redaction has multiple boxes
        
    Returns:
        list: List of SSE patch elements for DataStar
    """
    redactions_count = document.redactions.count()
    
    # Render list item HTML
    redaction_list_item_html = render_to_string(
        "redaction/redaction_list_item.html",
        {"redaction": redaction, "document": document}
    )
    
    # Build overlay HTML based on redaction type
    if is_multi_box and "boxes" in redaction.coordinates:
        overlay_html = ""
        for i, box in enumerate(redaction.coordinates["boxes"]):
            overlay_html += create_redaction_box_html(
                redaction_id=redaction.id,
                coordinates=box,
                page=redaction.coordinates["page"],
                redaction_type=redaction.redaction_type,
                is_multi_box=True,
                box_index=i,
            )
    else:
        overlay_html = create_redaction_box_html(
            redaction_id=redaction.id,
            coordinates=redaction.coordinates,
            page=redaction.coordinates["page"],
            redaction_type=redaction.redaction_type
        )
    
    # Build patch elements
    elements_to_patch = [
        # Update redaction count
        SSE.patch_elements(
            f'<span id="redaction-count" class="font-semibold">{redactions_count}</span>'
        ),
        # Add list item
        SSE.patch_elements(
            redaction_list_item_html,
            selector=REDACTIONS_LIST_SELECTOR,
            mode=ElementPatchMode.APPEND
        ),
        # Add overlay(s)
        SSE.patch_elements(
            overlay_html,
            selector=ANNOTATION_LAYER_SELECTOR,
            mode=ElementPatchMode.APPEND
        )
    ]
    
    # Remove empty state if this is the first redaction
    if redactions_count == 1:
        elements_to_patch.append(
            SSE.patch_elements(
                "",
                selector=EMPTY_REDACTIONS_SELECTOR,
                mode=ElementPatchMode.REMOVE
            )
        )
    
    return elements_to_patch


def create_multi_box_redaction(document, redaction_type, page, selections):
    """
    Create a single redaction with multiple coordinate boxes.
    
    Used when text selection spans multiple lines.
    
    Args:
        document (Document): Document model instance
        redaction_type (str): Type of redaction ("text" or "area")
        page (int): Page number
        selections (list): List of coordinate dictionaries
        
    Returns:
        Redaction: Created redaction instance
    """
    float_coords = {
        "page": page,
        "boxes": []
    }
    
    # Convert each selection to float coordinates
    for sel in selections:
        try:
            box_coords = convert_to_float_coords(sel)
            float_coords["boxes"].append(box_coords)
        except ValueError:
            # Skip invalid selections
            continue
    
    # Create redaction with multiple boxes
    return Redaction.objects.create(
        document=document,
        redaction_type=redaction_type,
        coordinates=float_coords
    )


def create_single_box_redaction(document, redaction_type, coordinates):
    """
    Create a single redaction with one coordinate box.
    
    Used for single-line text selections or area drawings.
    
    Args:
        document (Document): Document model instance
        redaction_type (str): Type of redaction ("text" or "area")
        coordinates (dict): Coordinate dictionary
        
    Returns:
        Redaction: Created redaction instance
    """
    float_coords = convert_to_float_coords(coordinates, page=coordinates.get("page"))
    
    return Redaction.objects.create(
        document=document,
        redaction_type=redaction_type,
        coordinates=float_coords
    )


def add_pdf_redaction_annotation(page, x, y, width, height):
    """
    Add a black rectangle annotation to a PDF page.
    
    Args:
        page: pypdf page object
        x, y, width, height: Coordinates in PDF space
    """
    redaction_annotation = DictionaryObject()
    redaction_annotation.update({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Square"),
        NameObject("/Rect"): ArrayObject([
            FloatObject(x), 
            FloatObject(y), 
            FloatObject(x + width), 
            FloatObject(y + height)
        ]),
        NameObject("/C"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),
        NameObject("/IC"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),
        NameObject("/BS"): DictionaryObject({
            NameObject("/W"): FloatObject(0),  # No border
        }),
    })
    
    if "/Annots" not in page:
        page[NameObject("/Annots")] = ArrayObject()
    page["/Annots"].append(redaction_annotation)


def create_notification_html(context, message):
    """
    Create a notification.
    
    Args:
        context (dict): Context dictionary for rendering the notification template
            notification_type (str): Type of notification ('success', 'error', etc.)
            notification_title (str): Notification title
        message (str): Notification message content
    """

    context = {
        "notification_type": context.get("notification_type"),
        "notification_title": context.get("notification_title"),
        "notification_message": message,
        # ...other context...
    }
    notification_html = render_to_string("redaction/notification.html", context)

    return SSE.patch_elements(
                notification_html,
                selector=NOTIFICATION_SELECTOR,
                mode=ElementPatchMode.APPEND,
            )


# ============================================================================
# VIEWS
# ============================================================================

def document_list(request):
    """
    Display list of all available documents.
    
    These documents are pre-seeded in the database for the assessment.
    """
    documents = Document.objects.all()
    return render(request, "redaction/document_list.html", {"documents": documents})


def document_detail(request, pk):
    """
    Display a specific document with PDF viewer interface.
    
    This view provides the main redaction interface where users can:
    - View the PDF document
    - Select text or draw areas to redact
    - See and manage existing redactions
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


@csrf_exempt
@require_http_methods(["POST"])
def redaction_create(request, document_id):
    """
    Create one or more redactions for a document.
    
    Accepts JSON data in the format:
    {
        "type": "text" or "area",
        "coordinates": {
            "page": 1,
            "x": 100, "y": 200, "width": 150, "height": 20,
            "selections": [...]  # Optional: for multi-line text selections
        }
    }
    
    Returns DataStar SSE response with HTML patches for:
    - Updated redaction count
    - New list item in sidebar
    - New overlay(s) on PDF
    """
    document = get_object_or_404(Document, pk=document_id)

    try:
        # Parse request data
        data = json.loads(request.body.decode("utf-8"))
        redaction_type = data.get("type")
        coordinates = data.get("coordinates")
        
        # Validate redaction type
        if redaction_type not in ("text", "area"):
            return DatastarResponse(create_notification_html(context={"notification_type": "error","notification_title": "Invalid"}, message="Invalid redaction type"))
        
        # Check for multi-line text selection
        selections = None
        if isinstance(coordinates, dict) and redaction_type == "text":
            selections = coordinates.get("selections")
        
        is_multi_box = selections and len(selections) > 1
        if is_multi_box:
            redaction = create_multi_box_redaction(
                document=document,
                redaction_type=redaction_type,
                page=coordinates.get("page"),
                selections=selections
            )
        else:
            # Extract single selection from array if present
            if selections and len(selections) == 1:
                single_coords = selections[0]
                single_coords["page"] = coordinates.get("page")
            else:
                single_coords = coordinates
            # Validate coordinates
            is_valid = validate_coordinates(single_coords)
            if not is_valid:
                return DatastarResponse(create_notification_html(context={"notification_type": "error","notification_title": "Invalid"}, message="Invalid coordinates"))
            # Validate page field
            if "page" not in single_coords:
                return DatastarResponse(create_notification_html(context={"notification_type": "error","notification_title": "No page field"}, message="Missing page field in coordinates."))
            try:
                redaction = create_single_box_redaction(
                    document=document,
                    redaction_type=redaction_type,
                    coordinates=single_coords
                )
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

        response = build_redaction_response(document, redaction, is_multi_box=is_multi_box)
        response.append(create_notification_html(context={"notification_type": "success","notification_title": "Redaction created!"}, message="Redaction created successfully."))
        return DatastarResponse(response)
        
    except json.JSONDecodeError:
        return DatastarResponse(create_notification_html(context={"notification_type": "error","notification_title": "JSON Decoder Error"}, message="Invalid JSON."))
    except Exception as e:
        import traceback
        print("[redaction_create] Exception:", e)
        traceback.print_exc()
        return DatastarResponse(create_notification_html(context={"notification_type": "error","notification_title": "Something went wrong!"}, message="Redaction was not created."))


@csrf_exempt
@require_http_methods(["DELETE"])
def redaction_delete(request, document_id, redaction_id):
    """
    Delete a redaction and all its associated overlays.
    
    For multi-box redactions, removes all overlay boxes.
    Returns DataStar SSE response with removal patches.
    """
    document = get_object_or_404(Document, pk=document_id)
    
    try:
        redaction = Redaction.objects.get(document=document, pk=redaction_id)

        # Build list of selectors to remove
        selectors_to_remove = [f"#redaction-item-{redaction.id}"]
        
        # Add overlay selectors based on redaction type
        if "boxes" in redaction.coordinates and redaction.coordinates["boxes"]:
            # Multi-box redaction: remove all boxes
            for i in range(len(redaction.coordinates["boxes"])):
                selectors_to_remove.append(f"#redaction-{redaction.id}-box-{i}")
        else:
            # Single-box redaction
            selectors_to_remove.append(f"#redaction-{redaction.id}")

        # Delete from database
        redaction.delete()
        redactions_count = document.redactions.count()

        # Build response patches
        elements_to_patch = [
            # Update count
            SSE.patch_elements(
                f'<span id="redaction-count" class="font-semibold">{redactions_count}</span>'
            )
        ]
        
        # Remove all related elements from DOM
        for selector in selectors_to_remove:
            elements_to_patch.append(
                SSE.patch_elements(selector=selector, mode=ElementPatchMode.REMOVE)
            )

        # Restore empty state if no redactions remain
        if redactions_count == 0:
            elements_to_patch.append(
                SSE.patch_elements(
                    render_to_string("redaction/empty_redaction_list.html"),
                    selector=REDACTIONS_LIST_SELECTOR,
                    mode=ElementPatchMode.APPEND
                )
            )

        elements_to_patch.append(create_notification_html(context={"notification_type": "success","notification_title": "Redaction deleted!"}, message="Redaction was deleted successfully."))
        return DatastarResponse(elements_to_patch)

    except Redaction.DoesNotExist:
        return JsonResponse({"error": "Redaction not found"}, status=404)
    except Exception as e:
        import traceback
        print("[redaction_delete] Exception:", e)
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=400)


def document_download_redacted(request, document_id):
    """
    Generate and download a PDF with all redactions applied as black boxes.
    
    Uses pypdf to add black rectangle annotations over redacted areas.
    Handles both single-box and multi-box redactions.
    """
    document = get_object_or_404(Document, pk=document_id)
    redactions = document.redactions.all()

    # Open and process the original PDF
    with Path(document.file.path).open("rb") as f:
        reader = PdfReader(f)
        writer = PdfWriter()

        # Process each page
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            page_height = float(page.mediabox.height)

            # Get redactions for this page (1-indexed in our model)
            page_redactions = redactions.filter(coordinates__page=page_num + 1)

            # Apply each redaction
            for redaction in page_redactions:
                coords = redaction.coordinates
                
                # Handle multi-box redactions
                if "boxes" in coords and coords["boxes"]:
                    for box in coords["boxes"]:
                        x, y, width, height = extract_pdf_coords(box, page_height)
                        add_pdf_redaction_annotation(page, x, y, width, height)
                # Handle single-box redactions
                else:
                    x, y, width, height = extract_pdf_coords(coords, page_height)
                    add_pdf_redaction_annotation(page, x, y, width, height)

            writer.add_page(page)

        # Create in-memory file
        output = BytesIO()
        writer.write(output)
        output.seek(0)

        # Return as downloadable file
        filename = f"{document.title}_redacted.pdf"
        return FileResponse(
            output,
            content_type="application/pdf",
            as_attachment=True,
            filename=filename
        )