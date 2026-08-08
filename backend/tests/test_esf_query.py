"""Unit tests for ESFQueryService — read-side queries, pagination, and snapshot integrity."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models import DocumentStatus
from app.services.esf_query_service import ESFQueryService

# ---- fixtures / helpers -----------------------------------------------

def _make_svc():
    """ESFQueryService with a mocked repository (no DB required)."""
    with patch("app.services.esf_query_service.ESFDocumentRepository"):
        svc = ESFQueryService(db=MagicMock())
    svc.repo.paginate_for_user.return_value = ([], 0)
    return svc


# ---- page() — parameter sanitization ----------------------------------

def test_page_clamps_page_size_max_to_200():
    svc = _make_svc()
    svc.page(user=MagicMock(), page_size=9999)
    assert svc.repo.paginate_for_user.call_args.kwargs["page_size"] == 200


def test_page_zero_page_size_defaults_to_25():
    # 0 is falsy → `int(page_size or 25)` picks the default, not the minimum
    svc = _make_svc()
    svc.page(user=MagicMock(), page_size=0)
    assert svc.repo.paginate_for_user.call_args.kwargs["page_size"] == 25


def test_page_explicit_1_page_size_accepted():
    svc = _make_svc()
    svc.page(user=MagicMock(), page_size=1)
    assert svc.repo.paginate_for_user.call_args.kwargs["page_size"] == 1


def test_page_enforces_minimum_page_1_on_negative():
    svc = _make_svc()
    svc.page(user=MagicMock(), page=-99)
    assert svc.repo.paginate_for_user.call_args.kwargs["page"] == 1


def test_page_rejects_unknown_sort_key():
    svc = _make_svc()
    svc.page(user=MagicMock(), sort="injection; DROP TABLE")
    assert svc.repo.paginate_for_user.call_args.kwargs["sort"] == "updated"


def test_page_accepts_all_valid_sort_keys():
    for key in ("created", "updated", "number", "status", "date", "supplier", "buyer"):
        svc = _make_svc()
        svc.page(user=MagicMock(), sort=key)
        assert svc.repo.paginate_for_user.call_args.kwargs["sort"] == key


def test_page_normalizes_invalid_direction_to_desc():
    svc = _make_svc()
    svc.page(user=MagicMock(), direction="INVALID")
    assert svc.repo.paginate_for_user.call_args.kwargs["direction"] == "desc"


def test_page_accepts_asc_direction():
    svc = _make_svc()
    svc.page(user=MagicMock(), direction="asc")
    assert svc.repo.paginate_for_user.call_args.kwargs["direction"] == "asc"


def test_page_strips_whitespace_from_search():
    svc = _make_svc()
    svc.page(user=MagicMock(), q="  строительные леса  ")
    assert svc.repo.paginate_for_user.call_args.kwargs["search"] == "строительные леса"


def test_page_blank_search_becomes_none():
    svc = _make_svc()
    svc.page(user=MagicMock(), q="   ")
    assert svc.repo.paginate_for_user.call_args.kwargs["search"] is None


def test_page_empty_search_becomes_none():
    svc = _make_svc()
    svc.page(user=MagicMock(), q="")
    assert svc.repo.paginate_for_user.call_args.kwargs["search"] is None


def test_page_total_pages_minimum_1_when_no_items():
    svc = _make_svc()
    result = svc.page(user=MagicMock())
    assert result["total_pages"] == 1
    assert result["total"] == 0


def test_page_calculates_total_pages_correctly():
    svc = _make_svc()
    svc.repo.paginate_for_user.return_value = ([], 51)
    result = svc.page(user=MagicMock(), page_size=25)
    assert result["total_pages"] == 3   # ceil(51 / 25) = 3


def test_page_returns_sort_and_direction_in_result():
    svc = _make_svc()
    result = svc.page(user=MagicMock(), sort="number", direction="asc")
    assert result["sort"] == "number"
    assert result["dir"] == "asc"


def test_page_status_filter_unknown_value_becomes_none():
    svc = _make_svc()
    svc.page(user=MagicMock(), status="NONEXISTENT")
    assert svc.repo.paginate_for_user.call_args.kwargs["status"] is None


def test_page_status_filter_valid_value_passed_as_enum():
    svc = _make_svc()
    svc.page(user=MagicMock(), status=DocumentStatus.PUBLISHED.value)
    assert svc.repo.paginate_for_user.call_args.kwargs["status"] == DocumentStatus.PUBLISHED


# ---- serialize_published() — snapshot integrity -----------------------

def test_serialize_published_raises_500_on_hash_mismatch():
    with patch("app.services.esf_query_service.ESFDocumentRepository"):
        svc = ESFQueryService(db=MagicMock())
    snap = MagicMock()
    snap.payload_json = {"uuid": "x", "number": "001"}
    snap.sha256 = "000deadbeef000_this_is_wrong"
    svc.repo.latest_snapshot.return_value = snap

    with pytest.raises(HTTPException) as exc:
        svc.serialize_published(MagicMock())
    assert exc.value.status_code == 500


def test_serialize_published_falls_back_to_serializer_without_snapshot():
    with patch("app.services.esf_query_service.ESFDocumentRepository"):
        svc = ESFQueryService(db=MagicMock())
    svc.repo.latest_snapshot.return_value = None
    doc = MagicMock()

    with patch.object(svc.serializer, "serialize", return_value={"fallback": True}) as mock_ser:
        result = svc.serialize_published(doc)

    mock_ser.assert_called_once_with(doc)
    assert result == {"fallback": True}


def test_serialize_published_returns_payload_on_valid_hash():
    from app.services import snapshot_service as ss

    with patch("app.services.esf_query_service.ESFDocumentRepository"):
        svc = ESFQueryService(db=MagicMock())
    payload = {"uuid": "abc", "number": "2026-001", "status": "первоначальный (Принят)"}
    snap = MagicMock()
    snap.payload_json = payload
    snap.sha256 = ss.content_hash(payload)
    svc.repo.latest_snapshot.return_value = snap

    result = svc.serialize_published(MagicMock())
    assert result == payload
