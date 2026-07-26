from typing import List, Optional

from app.models.document import Document
from sqlalchemy.orm import Session


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[Document]:
        return self.db.query(Document).order_by(Document.created_at.desc()).all()

    def get_by_id(self, doc_id: int) -> Optional[Document]:
        return self.db.query(Document).filter(Document.id == doc_id).first()

    def get_by_number(self, number: str) -> Optional[Document]:
        return self.db.query(Document).filter(Document.document_number == number).first()

    def create(self, doc: Document) -> Document:
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update(self, doc: Document) -> Document:
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def next_document_number(self) -> str:
        count = self.db.query(Document).count()
        return f"ESF-{count + 1:05d}"
