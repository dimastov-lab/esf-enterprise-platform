"""Snapshot Engine — freeze a published ESF into an immutable copy.

The snapshot stores the template-ready payload (the same dict the renderer uses)
plus a sha256 of its canonical form. Snapshots are write-once; mutation is blocked
at the ORM layer (see app/models/esf_snapshot.py).
"""
import hashlib
import json
import uuid as uuid_pkg

from app.models import ESFDocument, ESFSnapshot


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def make_snapshot(doc: ESFDocument, payload: dict) -> ESFSnapshot:
    return ESFSnapshot(
        document_id=doc.id,
        uuid=uuid_pkg.uuid4(),   # set in Python so it's accessible before flush
        payload_json=payload,
        sha256=content_hash(payload),
        immutable=True,
    )
