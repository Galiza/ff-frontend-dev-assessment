# ruff: noqa: E501

"""
Management command to create sample PDF documents and seed them into the database.
This creates 3 different legal-looking documents with multiple pages.
"""

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer

from frontend_dev_assessment.apps.redaction.models import Document

class Command(BaseCommand):
    help = "Create sample PDF documents and seed them into the database"
 
    def handle(self, *args, **options):  # noqa: ARG002
        self.stdout.write("Creating sample PDF documents...")

        # Ensure media directory exists
        media_root = settings.MEDIA_ROOT
        documents_dir = Path(media_root) / "documents"
        documents_dir.mkdir(parents=True, exist_ok=True)

        # Delete existing documents
        Document.objects.all().delete()
        self.stdout.write(self.style.WARNING("Deleted existing documents"))

        # Create three different documents
        documents_data = [
            {
                "title": "Employment Contract - Confidential",
                "content": self.get_employment_contract_content(),
                "filename": "employment_contract.pdf",
            },
            {
                "title": "Non-Disclosure Agreement (NDA)",
                "content": self.get_nda_content(),
                "filename": "nda_agreement.pdf",
            },
            {
                "title": "Settlement Agreement",
                "content": self.get_settlement_content(),
                "filename": "settlement_agreement.pdf",
            },
        ]

        for doc_data in documents_data:
            pdf_content = self.create_pdf(title=doc_data["title"], content=doc_data["content"])

            # Create document in database
            document = Document(title=doc_data["title"])
            document.file.save(doc_data["filename"], ContentFile(pdf_content), save=True)

            self.stdout.write(self.style.SUCCESS(f"✓ Created: {doc_data['title']}"))

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully created {len(documents_data)} sample documents!"))

    def create_pdf(self, title, content):
        """Create a PDF with the given title and content."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Container for the 'Flowable' objects
        elements = []

        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor="#000000",
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor="#000000",
            spaceAfter=12,
            spaceBefore=12,
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["BodyText"],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
        )

        # Add title
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.2 * inch))

        # Add content
        for section in content:
            if section["type"] == "heading":
                elements.append(Paragraph(section["text"], heading_style))
            elif section["type"] == "paragraph":
                elements.append(Paragraph(section["text"], body_style))
            elif section["type"] == "space":
                elements.append(Spacer(1, 0.2 * inch))
            elif section["type"] == "pagebreak":
                elements.append(PageBreak())

        # Build PDF
        doc.build(elements)

        # Get PDF content
        pdf_content = buffer.getvalue()
        buffer.close()

        return pdf_content

    def get_employment_contract_content(self):
        """Generate content for employment contract."""
        return [
            {"type": "heading", "text": "EMPLOYMENT AGREEMENT"},
            {"type": "space"},
            {
                "type": "paragraph",
                "text": 'This Employment Agreement (the "Agreement") is entered into as of January 15, 2024, by and between TechCorp Industries, Inc., a Delaware corporation (the "Company"), and Jane Smith, an individual residing at 123 Main Street, San Francisco, CA 94102 (the "Employee").',
            },
            {"type": "space"},
            {"type": "heading", "text": "1. POSITION AND DUTIES"},
            {
                "type": "paragraph",
                "text": "The Company hereby employs the Employee, and the Employee hereby accepts employment with the Company, as Senior Software Engineer. The Employee shall report to the Chief Technology Officer and shall perform such duties as are customarily associated with such position, including but not limited to software development, code review, and technical mentoring.",
            },
            {
                "type": "paragraph",
                "text": "The Employee agrees to devote their full business time, attention, and energies to the business of the Company and to perform their duties in a professional, ethical, and efficient manner.",
            },
            {"type": "space"},
            {"type": "heading", "text": "2. COMPENSATION"},
            {
                "type": "paragraph",
                "text": "As compensation for services rendered, the Company shall pay the Employee a base salary of $185,000 per annum, payable in accordance with the Company's standard payroll practices. The Employee's salary shall be subject to review annually.",
            },
            {
                "type": "paragraph",
                "text": "In addition to base salary, the Employee shall be eligible for an annual performance bonus of up to 20% of base salary, based on individual and company performance metrics as determined by the Company in its sole discretion.",
            },
            {"type": "pagebreak"},
            {"type": "heading", "text": "3. BENEFITS"},
            {
                "type": "paragraph",
                "text": "The Employee shall be entitled to participate in all employee benefit plans, practices, and programs maintained by the Company, including health insurance, dental insurance, vision insurance, 401(k) retirement plan, and paid time off, as in effect from time to time, on a basis commensurate with the Employee's position.",
            },
            {"type": "space"},
            {"type": "heading", "text": "4. CONFIDENTIALITY AND PROPRIETARY INFORMATION"},
            {
                "type": "paragraph",
                "text": "The Employee acknowledges that during their employment, they will have access to and become acquainted with various trade secrets and confidential information concerning the Company's business, including but not limited to customer lists, pricing information, software source code, technical specifications, and business strategies.",
            },
            {
                "type": "paragraph",
                "text": "The Employee agrees that they will not, during or after the term of employment, disclose any such confidential information to any person or entity, or use such information for their own benefit or the benefit of any third party, without the prior written consent of the Company.",
            },
            {"type": "space"},
            {"type": "heading", "text": "5. TERMINATION"},
            {
                "type": "paragraph",
                "text": "Either party may terminate this Agreement at any time, with or without cause, upon providing thirty (30) days written notice to the other party. Upon termination, the Employee shall return all Company property and confidential information in their possession.",
            },
            {"type": "pagebreak"},
            {"type": "heading", "text": "6. GOVERNING LAW"},
            {
                "type": "paragraph",
                "text": "This Agreement shall be governed by and construed in accordance with the laws of the State of California, without regard to its conflict of laws provisions.",
            },
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first above written.",
            },
            {"type": "space"},
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "_________________________<br/>TechCorp Industries, Inc.<br/>By: John Doe, CEO<br/>Date: January 15, 2024",
            },
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "_________________________<br/>Jane Smith, Employee<br/>Date: January 15, 2024",
            },
        ]

    def get_nda_content(self):
        """Generate content for NDA."""
        return [
            {"type": "heading", "text": "NON-DISCLOSURE AGREEMENT"},
            {"type": "space"},
            {
                "type": "paragraph",
                "text": 'This Non-Disclosure Agreement (the "Agreement") is entered into as of March 1, 2024, between Global Tech Solutions LLC, a California limited liability company with offices at 456 Innovation Drive, Palo Alto, CA 94301 (the "Disclosing Party"), and Robert Johnson, an individual with an address at 789 Elm Street, Mountain View, CA 94041 (the "Receiving Party").',
            },
            {"type": "space"},
            {"type": "heading", "text": "RECITALS"},
            {
                "type": "paragraph",
                "text": "WHEREAS, the Disclosing Party possesses certain confidential and proprietary information relating to its business, technology, and operations; and",
            },
            {
                "type": "paragraph",
                "text": "WHEREAS, the Receiving Party desires to receive certain confidential information from the Disclosing Party for the purpose of evaluating a potential business relationship;",
            },
            {
                "type": "paragraph",
                "text": "NOW, THEREFORE, in consideration of the mutual covenants and agreements contained herein, the parties agree as follows:",
            },
            {"type": "space"},
            {"type": "heading", "text": "1. DEFINITION OF CONFIDENTIAL INFORMATION"},
            {
                "type": "paragraph",
                "text": '"Confidential Information" means all information, whether written, oral, electronic, or visual, disclosed by the Disclosing Party to the Receiving Party, including but not limited to: (a) technical data, trade secrets, know-how, research, product plans, products, services, customers, customer lists, markets, software, developments, inventions, processes, formulas, technology, designs, drawings, engineering, hardware configuration information, marketing, finances, or other business information.',
            },
            {"type": "pagebreak"},
            {"type": "heading", "text": "2. OBLIGATIONS OF RECEIVING PARTY"},
            {
                "type": "paragraph",
                "text": "The Receiving Party agrees to: (a) hold and maintain the Confidential Information in strictest confidence; (b) not disclose the Confidential Information to any third parties without the prior written consent of the Disclosing Party; (c) not use the Confidential Information for any purpose except as specifically contemplated by the parties; and (d) protect the Confidential Information using the same degree of care it uses to protect its own confidential information, but in no event less than reasonable care.",
            },
            {"type": "space"},
            {"type": "heading", "text": "3. EXCLUSIONS FROM CONFIDENTIAL INFORMATION"},
            {
                "type": "paragraph",
                "text": "Confidential Information shall not include information that: (a) is or becomes publicly available without breach of this Agreement; (b) was rightfully in the Receiving Party's possession prior to disclosure by the Disclosing Party; (c) is rightfully received by the Receiving Party from a third party without breach of any confidentiality obligation; or (d) is independently developed by the Receiving Party without use of or reference to the Confidential Information.",
            },
            {"type": "space"},
            {"type": "heading", "text": "4. TERM AND TERMINATION"},
            {
                "type": "paragraph",
                "text": "This Agreement shall commence on the date first written above and shall continue for a period of five (5) years. The obligations of confidentiality shall survive termination of this Agreement and shall continue for an additional three (3) years thereafter.",
            },
            {"type": "pagebreak"},
            {"type": "heading", "text": "5. RETURN OF MATERIALS"},
            {
                "type": "paragraph",
                "text": "Upon termination of this Agreement or upon request by the Disclosing Party, the Receiving Party shall promptly return all documents, materials, and other tangible items containing or representing Confidential Information, and all copies thereof, or shall certify in writing that all such materials have been destroyed.",
            },
            {"type": "space"},
            {"type": "heading", "text": "6. REMEDIES"},
            {
                "type": "paragraph",
                "text": "The Receiving Party acknowledges that unauthorized disclosure or use of Confidential Information may cause irreparable harm to the Disclosing Party for which monetary damages may be inadequate. Accordingly, the Disclosing Party shall be entitled to seek equitable relief, including injunction and specific performance, in addition to all other remedies available at law or in equity.",
            },
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first above written.",
            },
            {"type": "space"},
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "_________________________<br/>Global Tech Solutions LLC<br/>By: Sarah Williams, General Counsel<br/>Date: March 1, 2024",
            },
            {"type": "space"},
            {"type": "paragraph", "text": "_________________________<br/>Robert Johnson<br/>Date: March 1, 2024"},
        ]

    def get_settlement_content(self):
        """Generate content for settlement agreement."""
        return [
            {"type": "heading", "text": "SETTLEMENT AND RELEASE AGREEMENT"},
            {"type": "space"},
            {
                "type": "paragraph",
                "text": 'This Settlement and Release Agreement (the "Agreement") is entered into as of June 15, 2024, by and between Michael Anderson, an individual residing at 321 Oak Avenue, Seattle, WA 98101 (the "Claimant"), and Acme Corporation, a Washington corporation with its principal place of business at 555 Business Park Drive, Bellevue, WA 98004 (the "Company").',
            },
            {"type": "space"},
            {"type": "heading", "text": "RECITALS"},
            {
                "type": "paragraph",
                "text": "WHEREAS, the Claimant was employed by the Company from January 2020 through December 2023;",
            },
            {
                "type": "paragraph",
                "text": 'WHEREAS, certain disputes and claims have arisen between the parties relating to the Claimant\'s employment and termination thereof (the "Disputes");',
            },
            {
                "type": "paragraph",
                "text": "WHEREAS, the parties wish to resolve all Disputes between them without the necessity of litigation and to avoid the expense and uncertainty of litigation;",
            },
            {
                "type": "paragraph",
                "text": "NOW, THEREFORE, in consideration of the mutual promises, covenants, and agreements set forth herein, the parties agree as follows:",
            },
            {"type": "space"},
            {"type": "heading", "text": "1. SETTLEMENT PAYMENT"},
            {
                "type": "paragraph",
                "text": 'In full and complete settlement of all claims, the Company agrees to pay the Claimant the sum of Seventy-Five Thousand Dollars ($75,000.00) (the "Settlement Payment"). The Settlement Payment shall be paid within fifteen (15) business days of the execution of this Agreement by both parties.',
            },
            {"type": "pagebreak"},
            {"type": "heading", "text": "2. GENERAL RELEASE BY CLAIMANT"},
            {
                "type": "paragraph",
                "text": "In consideration of the Settlement Payment and the other terms of this Agreement, the Claimant, on behalf of themselves and their heirs, executors, administrators, successors, and assigns, hereby irrevocably and unconditionally releases, acquits, and forever discharges the Company, its officers, directors, employees, agents, shareholders, parent companies, subsidiaries, affiliates, predecessors, successors, and assigns from any and all claims, demands, damages, debts, liabilities, accounts, obligations, costs, expenses, liens, actions, and causes of action of every kind and nature whatsoever, whether known or unknown, suspected or unsuspected, which the Claimant has or may have against the Company.",
            },
            {
                "type": "paragraph",
                "text": "This release includes, but is not limited to, claims arising under federal, state, or local laws prohibiting employment discrimination, claims for wrongful discharge, breach of contract, breach of the implied covenant of good faith and fair dealing, negligence, defamation, emotional distress, and any other common law or statutory claims.",
            },
            {"type": "space"},
            {"type": "heading", "text": "3. NON-ADMISSION"},
            {
                "type": "paragraph",
                "text": "This Agreement is entered into as a compromise and settlement of disputed claims. Nothing contained herein shall be construed as an admission by either party of any liability, wrongdoing, or violation of law. The Company specifically denies any liability or wrongdoing with respect to the Claimant's employment or termination.",
            },
            {"type": "pagebreak"},
            {"type": "heading", "text": "4. CONFIDENTIALITY"},
            {
                "type": "paragraph",
                "text": "The parties agree that the terms and conditions of this Agreement, including but not limited to the amount of the Settlement Payment, shall be kept strictly confidential. Neither party shall disclose the existence or terms of this Agreement to any third party, except as required by law or except to their attorneys, accountants, tax advisors, or immediate family members, who shall also be bound by this confidentiality provision.",
            },
            {"type": "space"},
            {"type": "heading", "text": "5. NON-DISPARAGEMENT"},
            {
                "type": "paragraph",
                "text": "The Claimant agrees not to make any disparaging or negative statements, written or oral, about the Company, its officers, directors, employees, products, services, or business practices. The Company agrees to instruct its officers and directors not to make any disparaging or negative statements about the Claimant.",
            },
            {"type": "space"},
            {"type": "heading", "text": "6. GOVERNING LAW"},
            {
                "type": "paragraph",
                "text": "This Agreement shall be governed by and construed in accordance with the laws of the State of Washington, without regard to its conflict of laws principles.",
            },
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first above written.",
            },
            {"type": "space"},
            {"type": "space"},
            {
                "type": "paragraph",
                "text": "_________________________<br/>Acme Corporation<br/>By: David Martinez, Chief Legal Officer<br/>Date: June 15, 2024",
            },
            {"type": "space"},
            {"type": "paragraph", "text": "_________________________<br/>Michael Anderson<br/>Date: June 15, 2024"},
        ]
