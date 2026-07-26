"""Domain enumerations for the ESF schema."""
import enum


class DocumentStatus(str, enum.Enum):
    """ESF document lifecycle (STI-007)."""
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class PartyType(str, enum.Enum):
    """Supplier (поставщик) / Buyer (покупатель)."""
    SUPPLIER = "SUPPLIER"
    BUYER = "BUYER"
