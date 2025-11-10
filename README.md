# Frontend Developer Assessment - PDF Redaction Tool

## Overview

Welcome to the Frontend Developer Assessment! This project is designed to evaluate your ability to build interactive web interfaces using a **hypermedia-first approach** with **DataStar**, while demonstrating good judgment about when alternative tools might be more appropriate.

### What You're Building

You'll be implementing a **PDF redaction tool** that allows users to:

- View PDF documents in the browser
- Mark content for redaction using two methods:
  - **Text selection**: Select text passages to redact
  - **Area drawing**: Draw rectangular boxes over images/diagrams
- View and manage a list of all redactions
- Easily switch between text selection and area drawing modes
- Download a redacted version of the PDF

### The Challenge

The primary goal is to implement the user interface using **DataStar** (a hypermedia framework). However, you may encounter parts of the interface that are genuinely difficult or awkward to implement with pure hypermedia. In those cases, you're welcome to use **React** or other JavaScript tools—but you must justify your choice.

**This assessment tests:**
- Your understanding of hypermedia-driven interfaces
- Your ability to work with modern frontend tools (PDF.js, DataStar)
- Your judgment about technology choices
- Your code quality and attention to UI/UX

### Freedom to Customize

**Important:** The provided scaffolding, styling, and structure are merely suggestions to help you get started quickly. You are **completely free** to:

- Change the styling
- Restructure the HTML templates
- Modify the backend if needed
- Add or remove dependencies
- Reorganize the project layout
- Implement your own design system

Think of this as a starting point, not a constraint. We want to see **your** approach to building this feature. The core requirement is implementing the PDF redaction functionality, how you get there is up to you.

---

## Getting Started

### Prerequisites

- **Python 3.12+** 
- **uv** (Python package manager) - Install from [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- A modern web browser (Chrome, Firefox, Safari, or Edge)

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd ff-frontend-dev-assessment
```

2. **Install dependencies using uv**

```bash
uv sync
```

This will create a virtual environment and install all required packages.

3. **Run database migrations**

```bash
uv run python manage.py migrate
```

4. **Seed sample documents**

Three sample legal documents (PDFs) are provided. Run the seed command to create them:

```bash
uv run python manage.py seed_documents
```

This creates:
- Employment Contract - Confidential
- Non-Disclosure Agreement (NDA)
- Settlement Agreement

5. **Start the development server**

```bash
uv run python manage.py runserver
```

6. **Open your browser**

Navigate to [http://localhost:8000](http://localhost:8000)

You should see a list of the three sample documents. Click on any document to begin implementing the redaction interface.

---

## Your Task

### Required Features

#### 1. PDF Viewer (PDF.js)

Implement a PDF viewer in `document_detail.html` that:

- Loads and displays the PDF from `{{ document.file.url }}`
- Renders all pages of the document
- Provides basic navigation (if multi-page)

**Resources:**
- [PDF.js Documentation](https://mozilla.github.io/pdf.js/)
- [PDF.js Examples](https://mozilla.github.io/pdf.js/examples/)
- PDF.js is already included via CDN in `base.html`

#### 2. Redaction Modes

Implement two modes that users can easily switch between.

**Text Selection Mode:**
- Users can select text on the PDF
- When text is selected, create a redaction box around it
- Send coordinates to the backend

**Area Drawing Mode:**
- Users can click and drag to draw rectangular areas
- These rectangles mark areas for redaction (for images, diagrams, etc.)
- Send coordinates to the backend

#### 3. Creating Redactions (DataStar)

When a user creates a redaction (either via text selection or area drawing):

1. Capture the coordinates: `{x, y, width, height, page}`
2. Send a POST request to: `/document/<id>/redactions/create/`
3. Use DataStar's reactive features to update the UI
4. Update the redactions list without a full page reload

**Backend endpoint details** (already implemented):
```
POST /document/<document_id>/redactions/create/

Expected payload (JSON):
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
```

#### 4. Redactions List (DataStar)

Display a live-updated list of all redactions:

- Show each redaction with its type, page, and coordinates
- The list should update automatically when redactions are added or deleted
- The partial template `redaction_list.html` is already provided

#### 5. Visual Feedback

- Display redaction boxes as overlays on the PDF
- Use different visual styles for text vs. area redactions
- Highlight the current mode (text selection vs. area drawing)
- Show loading states where appropriate

#### 6. Download Redacted PDF (already implemented)

The download button is already wired up. The backend:
- Generates a PDF with black boxes over redacted areas
- Uses pypdf to apply redactions
- Returns the file for download

---

## Evaluation Criteria

We'll be evaluating your submission based on:

- Does the PDF viewer work correctly?
- Can users create redactions using both modes?
- Does the redactions list update dynamically?
- Is the code well-organized and maintainable?
- Did you use DataStar effectively for appropriate interactions?
- Do you understand when hypermedia is and isn't suitable?
- Are your technology choices well-justified?
- Is the interface intuitive and easy to use?
- Are there clear visual indicators for modes and actions?
- Does the UI provide appropriate feedback?
- Are error states handled gracefully?
- Is the code clean and readable?
- Are there helpful comments where needed?
- Is the code organized logically?
- Are there any obvious bugs or issues?

---

## Admin Access (Optional)

If you want to explore the Django admin:

```bash
uv run python manage.py createsuperuser
```

Then navigate to [http://localhost:8000/admin](http://localhost:8000/admin) to view and manage documents and redactions.

---

## Good Luck!

We're excited to see your implementation. Remember:

- **Hypermedia first**, but use the right tool for the job
- **UX matters** - think about the user experience
- **Code quality counts** - write code you'd want to maintain
- **Justify your choices** - explain your reasoning

If you have any questions about the requirements, please reach out.

Happy coding! 🚀
