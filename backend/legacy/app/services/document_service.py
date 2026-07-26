import os
from typing import List, Optional

import qrcode
from app.models.document import Document, DocumentStatus
from app.repositories.document_repository import DocumentRepository
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "storage")
PDF_DIR = os.path.join(STORAGE_DIR, "pdf")
QR_DIR = os.path.join(STORAGE_DIR, "qr")


class DocumentService:
    def __init__(self, db: Session):
        self.repo = DocumentRepository(db)

    def list_all(self) -> List[Document]:
        return self.repo.get_all()

    def get(self, doc_id: int) -> Optional[Document]:
        return self.repo.get_by_id(doc_id)

    def get_by_number(self, number: str) -> Optional[Document]:
        return self.repo.get_by_number(number)

    def create_draft(
        self,
        title: str,
        applicant_name: str,
        applicant_id: str,
        description: str,
        created_by: int,
    ) -> Document:
        doc = Document(
            title=title,
            applicant_name=applicant_name,
            applicant_id=applicant_id,
            document_number=self.repo.next_document_number(),
            description=description,
            status=DocumentStatus.DRAFT,
            created_by=created_by,
        )
        return self.repo.create(doc)

    def generate(self, doc_id: int, base_url: str) -> Document:
        doc = self.repo.get_by_id(doc_id)
        if not doc:
            raise ValueError("Document not found")

        os.makedirs(PDF_DIR, exist_ok=True)
        os.makedirs(QR_DIR, exist_ok=True)

        public_url = f"{base_url}/public/{doc.document_number}"
        qr_path = os.path.join(QR_DIR, f"{doc.document_number}.png")
        self._generate_qr(public_url, qr_path)

        pdf_path = os.path.join(PDF_DIR, f"{doc.document_number}.pdf")
        self._generate_pdf(doc, pdf_path, qr_path, public_url)

        doc.pdf_path = pdf_path
        doc.qr_path = qr_path
        doc.status = DocumentStatus.PUBLISHED
        return self.repo.update(doc)

    def _generate_qr(self, url: str, path: str) -> None:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(path)

    def _generate_pdf(self, doc: Document, pdf_path: str, qr_path: str, public_url: str) -> None:
        pdf = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=16, spaceAfter=12
        )
        label_style = ParagraphStyle(
            "Label", parent=styles["Normal"], fontSize=10, textColor=colors.grey
        )
        value_style = ParagraphStyle(
            "Value", parent=styles["Normal"], fontSize=12, spaceAfter=8
        )
        small_style = ParagraphStyle(
            "Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey, alignment=TA_CENTER
        )

        story = []
        story.append(Paragraph("ELECTRONIC SUBMISSION FORM", title_style))
        story.append(Paragraph(f"Document № {doc.document_number}", styles["Heading2"]))
        story.append(Spacer(1, 0.5 * cm))

        data = [
            ["Field", "Value"],
            ["Document Number", doc.document_number],
            ["Title", doc.title],
            ["Applicant Name", doc.applicant_name],
            ["Applicant ID", doc.applicant_id],
            ["Status", doc.status.value],
            ["Created", doc.created_at.strftime("%Y-%m-%d %H:%M")],
        ]
        if doc.description:
            data.append(["Description", doc.description])

        table = Table(data, colWidths=[5 * cm, 12 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(table)
        story.append(Spacer(1, 1 * cm))

        if os.path.exists(qr_path):
            qr_img = Image(qr_path, width=4 * cm, height=4 * cm)
            qr_table = Table([[qr_img]], colWidths=[17 * cm])
            qr_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(qr_table)
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(f"Scan to verify: {public_url}", small_style))

        pdf.build(story)
