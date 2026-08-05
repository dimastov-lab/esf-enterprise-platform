"""Model registry.

Importing this package imports every model, ensuring `Base.metadata` is fully
populated (required for Alembic autogenerate and for relationship resolution).
"""
from app.db.base import Base
from app.models.api_credential import ApiCredential
from app.models.audit_log import AuditLog
from app.models.counterparty import Counterparty
from app.models.enums import DocumentStatus, PartyType
from app.models.esf_document import ESFDocument
from app.models.esf_item import ESFItem
from app.models.esf_party import ESFParty
from app.models.esf_signature import ESFSignature
from app.models.esf_snapshot import ESFSnapshot
from app.models.esf_supply_info import ESFSupplyInfo
from app.models.esf_totals import ESFTotals
from app.models.good import Good
from app.models.organization import Organization
from app.models.user import Role, User, user_roles

__all__ = [
    "Base",
    "DocumentStatus",
    "PartyType",
    "User",
    "Role",
    "user_roles",
    "ApiCredential",
    "Organization",
    "ESFDocument",
    "ESFParty",
    "ESFSupplyInfo",
    "ESFItem",
    "ESFTotals",
    "ESFSignature",
    "ESFSnapshot",
    "AuditLog",
    "Counterparty",
    "Good",
]
