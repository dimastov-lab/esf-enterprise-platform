"""Full regression suite (Sprint 12R).

Covers: health, auth + RBAC, CRUD + totals, validation, publish + snapshot,
immutability, PDF, QR, public verification, autosave, dashboard polish.
All tests run inside a rolled-back transaction (see conftest.py).
"""
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.main import app

FORM = {"content-type": "application/x-www-form-urlencoded"}


def valid_pairs(**override):
    pairs = [
        ("supplier_inn", "01610201710254"), ("supplier_name", 'ООО "Ава Тур"'),
        ("supplier_address", "г. Бишкек"), ("supplier_tax_office", "УГНС"),
        ("supplier_bank", "Бакай Банк"), ("supplier_account", "1240020001699526"),
        ("buyer_inn", "6686063027"), ("buyer_name", 'ООО "Промснабметалл"'),
        ("buyer_address", "Екатеринбург"), ("buyer_tax_office", "643 - РФ"),
        ("buyer_bank", "ОТП"), ("buyer_account", "40702810408170002241"),
        ("supply_date", "24.05.2026"), ("supply_type", "экспорт"),
        ("payment_type", "Безналичная"), ("contract_number", "23/04-26"),
        ("contract_date", "23.04.2026"), ("currency_code", "643"),
        ("currency_rate", "1.2263"), ("director_name", "Дуйшекеев Б.К."),
        ("item_tnved", "7308400009"), ("item_name", "Строительные леса"),
        ("item_unit", "Килограмм"), ("item_price", "116.49850"),
        ("item_qty", "21000.00000"), ("item_vat_rate", "0"),
        ("item_vat_amount", "0"), ("item_nsp", "0"),
    ]
    if override:
        pairs = [(k, override.get(k, v)) for k, v in pairs]
    return pairs


def new_draft(c):
    return c.get("/esf/new").url.path.split("/")[-1]


def save(c, uuid, pairs):
    return c.post(f"/esf/{uuid}/save", content=urlencode(pairs), headers=FORM)


def test_new_draft_carries_over_supplier(admin):
    """A new draft prefills the supplier from the user's most recent document
    (the supplier is almost always the same organisation)."""
    first = new_draft(admin)
    save(admin, first, valid_pairs())
    second = new_draft(admin)
    page = admin.get(f"/esf/{second}").text
    # supplier prefilled, buyer still blank
    assert 'name="supplier_inn" value="01610201710254"' in page
    assert 'name="supplier_name" value="ООО &#34;Ава Тур&#34;"' in page or 'ООО "Ава Тур"' in page
    assert 'name="buyer_inn" value=""' in page


def test_duplicate_creates_editable_copy(admin, db_session):
    import uuid as U

    from app.models import DocumentStatus, ESFDocument
    src = new_draft(admin)
    save(admin, src, valid_pairs())
    admin.post(f"/esf/{src}/publish", content=urlencode(valid_pairs()), headers=FORM)
    # duplicate the (now published) document
    r = admin.post(f"/esf/{src}/duplicate")
    assert r.status_code == 200          # followed redirect to the new draft editor
    new_uuid = r.url.path.split("/")[-1]
    assert new_uuid != src
    new = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(new_uuid)).one()
    # copy is a fresh editable draft: same parties/items, but no number/snapshot
    assert new.status == DocumentStatus.DRAFT and new.esf_number is None and not new.snapshots
    parties = {p.party_type.value: p for p in new.parties}
    assert parties["SUPPLIER"].inn == "01610201710254"
    assert any(it.product_name for it in new.items)
    # source document is untouched (still published)
    srcdoc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(src)).one()
    assert srcdoc.status == DocumentStatus.PUBLISHED


def test_published_form_matches_gns_formatting(admin):
    """Compliance: the published form must print price/quantity with 5 decimals
    (e.g. 100.00000) and the footer timestamp with dotted time (13.46.33),
    matching the official salyk.kg STI-007."""
    import re
    uuid = new_draft(admin)
    pairs = valid_pairs(item_price="100", item_qty="3")
    save(admin, uuid, pairs)
    admin.post(f"/esf/{uuid}/publish", content=urlencode(pairs), headers=FORM)
    text = admin.get(f"/esf/{uuid}").text
    assert "100.00000" in text and "3.00000" in text          # price / qty → 5 decimals
    assert re.search(r"\d{2}/\d{2}/\d{4}\s+\d{2}\.\d{2}\.\d{2}", text)  # dd/mm/yyyy hh.mm.ss
    assert not re.search(r"\d{2}:\d{2}:\d{2}", text)          # no colon-time


def _all_fields_pairs():
    """Every editable STI-007 field with a unique marker value (Ω) so we can
    trace each one through save → snapshot → public → PDF."""
    return [
        ("supplier_inn", "01610201710254"), ("supplier_name", "ПОСТ-НЕЙМ-Ω"),
        ("supplier_branch_inn", "22222222222222"), ("supplier_branch", "ФИЛ-ПОСТ-Ω"),
        ("supplier_address", "АДР-ПОСТ-Ω"), ("supplier_tax_office_code", "004"),
        ("supplier_tax_office", "НАЛОГ-ПОСТ-Ω"), ("supplier_bank", "БАНК-ПОСТ-Ω"),
        ("supplier_account", "11110000111100001111"),
        ("buyer_inn", "6686063027"), ("buyer_name", "ПОК-НЕЙМ-Ω"),
        ("buyer_branch_inn", "33333333333333"), ("buyer_branch", "ФИЛ-ПОК-Ω"),
        ("buyer_address", "АДР-ПОК-Ω"), ("buyer_tax_office", "НАЛОГ-ПОК-Ω"),
        ("buyer_bank", "БАНК-ПОК-Ω"), ("buyer_account", "22220000222200002222"),
        ("issue_date", "29.05.2026"),
        ("supply_date", "24.05.2026"), ("supply_type", "ВИД-Ω"),
        ("payment_type", "ОПЛАТА-Ω"), ("note", "ПРИМ-Ω"),
        ("contract_number", "ДОГ-Ω-123"), ("contract_date", "23.04.2026"),
        ("currency_code", "643"), ("currency_rate", "1.2263"),
        ("director_name", "ПОДПИСАНТ-Ω"),
        ("item_tnved", "7308400009"), ("item_name", "ТОВАР-Ω"),
        ("item_unit", "ЕД-Ω"), ("item_price", "116.49850"), ("item_qty", "21000.00000"),
        # rate 0 keeps VAT (0) consistent with the base — the rate isn't a traced
        # Ω-marker; VAT consistency is exercised by test_validation_new_rules.
        ("item_vat_rate", "0"), ("item_vat_amount", "0"), ("item_nsp", "0"),
        ("item_customs", "ТАМОЖ-Ω-456"),
    ]


def test_all_sti007_fields_round_trip(admin, db_session, anon):
    """Field compliance: every STI-007 field must survive save → snapshot →
    public page → PDF (the snapshot is the authoritative source for both)."""
    import io
    import json
    import uuid as U

    from app.models import ESFDocument
    pairs = _all_fields_pairs()
    u = new_draft(admin)
    save(admin, u, pairs)
    admin.post(f"/esf/{u}/publish", content=urlencode(pairs), headers=FORM)

    doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(u)).one()
    blob = json.dumps(doc.snapshots[0].payload_json, ensure_ascii=False)
    for k, v in pairs:
        if k in ("item_vat_amount", "item_nsp"):
            continue  # zero -> formatted "0.00"; not a unique marker
        assert v in blob or v.replace(".", "") in blob, f"field {k}={v} missing from snapshot"

    pub = anon.get(f"/esf/check-esf?documentUUID={u}").text   # rendered on the public page
    for marker in ("ПОСТ-НЕЙМ-Ω", "ПОК-НЕЙМ-Ω", "АДР-ПОСТ-Ω", "НАЛОГ-ПОСТ-Ω", "БАНК-ПОК-Ω",
                   "ВИД-Ω", "ОПЛАТА-Ω", "ПРИМ-Ω", "ДОГ-Ω-123", "ПОДПИСАНТ-Ω", "ТОВАР-Ω", "ТАМОЖ-Ω-456"):
        assert marker in pub, f"marker {marker} missing from public page"

    pdf = admin.get(f"/pdf/{u}.pdf").content                  # same template -> PDF
    from pypdf import PdfReader
    txt = PdfReader(io.BytesIO(pdf)).pages[0].extract_text() or ""
    assert "ПОДПИСАНТ" in txt and "ТОВАР" in txt and "ПРИМ" in txt


# ---- health -----------------------------------------------------------
def test_health():
    assert TestClient(app).get("/").json()["status"] == "running"


def test_official_font_bundled_and_served():
    # The document font must match the official form (DejaVu Sans, embedded in the reference PDF).
    c = TestClient(app)
    r = c.get("/static/fonts/DejaVuSans.ttf")
    assert r.status_code == 200 and r.content[:4] in (b"\x00\x01\x00\x00", b"true", b"OTTO")
    css = c.get("/static/css/esf_form.css").text
    assert "DejaVu Sans" in css and "DejaVuSans.ttf" in css


# ---- auth + RBAC ------------------------------------------------------
def test_protected_redirects_when_anonymous(anon):
    r = anon.get("/dashboard")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_wrong_credentials(anon):
    assert anon.post("/login", data={"username": "t_admin", "password": "bad"}).status_code == 401


def test_admin_can_reach_user_admin(admin):
    assert admin.get("/admin/users").status_code == 200


def test_issuer_forbidden_from_admin(issuer):
    assert issuer.get("/admin/users").status_code == 403


def test_rbac_scoping(admin, issuer):
    # issuer creates a doc; admin sees it, a second issuer would not
    uuid = new_draft(issuer)
    save(issuer, uuid, valid_pairs())
    assert issuer.get("/dashboard").text.count(uuid) >= 1
    assert admin.get("/dashboard").text.count(uuid) >= 1  # admin sees all


# ---- CRUD + totals ----------------------------------------------------
def test_create_save_reload_restores(admin):
    uuid = new_draft(admin)
    assert save(admin, uuid, valid_pairs()).status_code in (200, 303)
    body = admin.get(f"/esf/{uuid}").text
    for needle in ["01610201710254", "Строительные леса", "116.49850", "2446468.50"]:
        assert needle in body


def test_totals_recompute(admin):
    uuid = new_draft(admin)
    pairs = valid_pairs(item_price="100", item_qty="10", item_vat_amount="120")
    save(admin, uuid, pairs)
    body = admin.get(f"/esf/{uuid}").text
    assert "1000.00" in body and "120.00" in body and "1120.00" in body


# ---- validation -------------------------------------------------------
def test_validation_blocks_publish(admin):
    uuid = new_draft(admin)
    r = admin.post(f"/esf/{uuid}/publish",
                   content=urlencode([("currency_code", "643")]), headers=FORM)
    assert r.status_code == 200 and "Невозможно сформировать" in r.text


# ---- publish + snapshot ----------------------------------------------
def test_publish_creates_snapshot_and_number(admin, db_session):
    import uuid as U

    from app.models import DocumentStatus, ESFDocument
    from app.services.snapshot_service import content_hash
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    r = admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    # Phase 9: publish opens the final document directly (no intermediate result page)
    assert r.url.path == f"/esf/{uuid}"
    assert "viewer-bar" in r.text and "Печать" in r.text   # official viewer toolbar present
    doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    assert doc.status == DocumentStatus.PUBLISHED and doc.esf_number and doc.published_at
    assert len(doc.snapshots) == 1
    snap = doc.snapshots[0]
    assert len(snap.sha256) == 64 and snap.sha256 == content_hash(snap.payload_json)
    assert snap.payload_json["number"] == doc.esf_number and snap.payload_json["published"] is True
    # official salyk.kg number format: 000{YYYY}-004-{8 digits}
    import re
    assert re.fullmatch(r"000\d{4}-004-\d{8}", doc.esf_number), doc.esf_number


def test_publish_is_atomic_when_snapshot_fails(monkeypatch):
    """If snapshot/QR creation fails mid-publish, the WHOLE publication rolls
    back: the document stays unpublished with no snapshot — never a PUBLISHED
    document without its immutable snapshot.

    Uses its own real transaction (not the savepoint harness) so the service's
    own rollback is exercised honestly; cleans up the rows it created.
    """
    import uuid as U

    import pytest
    from sqlalchemy.orm import Session
    from starlette.datastructures import FormData

    from app.db.session import engine
    from app.models import DocumentStatus, ESFDocument, User
    from app.services import snapshot_service
    from app.services.auth_service import ROLE_ADMIN, AuthService
    from app.services.esf_service import ESFService

    s = Session(bind=engine)
    uname = "atomic_" + U.uuid4().hex[:10]
    user = doc = None
    try:
        AuthService(s).create_user(uname, "pw", ROLE_ADMIN)
        s.commit()
        user = s.query(User).filter(User.username == uname).one()
        svc = ESFService(s)
        doc = svc.create_draft(user)                         # committed DRAFT
        svc.save(doc, user, FormData(valid_pairs()))         # committed, valid data
        doc_id = doc.id

        monkeypatch.setattr(
            snapshot_service, "make_snapshot",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated snapshot/QR failure")))
        with pytest.raises(RuntimeError):
            svc.publish(doc, user)

        s.expire_all()
        after = s.get(ESFDocument, doc_id)
        assert after is not None                              # document still exists
        assert after.status != DocumentStatus.PUBLISHED       # remains DRAFT/VALIDATED
        assert after.published_at is None
        assert after.esf_number is None                       # number assignment rolled back too
        assert not after.snapshots                            # no partial snapshot
    finally:
        try:
            if doc is not None:
                d = s.get(ESFDocument, doc.id)
                if d is not None:
                    s.delete(d); s.commit()                   # cascade removes children
        except Exception:
            s.rollback()
        try:
            if user is not None:
                u = s.get(User, user.id)
                if u is not None:
                    s.delete(u); s.commit()
        except Exception:
            s.rollback()
        s.close()


def test_published_doc_always_has_snapshot(admin, db_session):
    """Invariant: a PUBLISHED document always carries an immutable snapshot, so the
    public page never serves a published doc without one."""
    import uuid as U

    from app.models import DocumentStatus, ESFDocument
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    assert doc.status == DocumentStatus.PUBLISHED and len(doc.snapshots) >= 1


def test_cancel_published_keeps_snapshot(admin, db_session):
    """v6.0: annulling a PUBLISHED ESF sets CANCELLED + cancelled_at and PRESERVES
    the immutable snapshot. A second cancel is rejected (409)."""
    import uuid as U

    from app.models import DocumentStatus, ESFDocument
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    r = admin.post(f"/esf/{uuid}/cancel")
    assert "Аннулирован" in r.text                     # view shows cancelled status
    db_session.expire_all()
    doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    assert doc.status == DocumentStatus.CANCELLED and doc.cancelled_at is not None
    assert len(doc.snapshots) == 1                      # snapshot preserved (history intact)
    assert admin.post(f"/esf/{uuid}/cancel").status_code == 409   # already cancelled


def test_correction_creates_linked_draft(admin, db_session):
    """v6.0: a correction is a new editable DRAFT linked to the published original
    (corrects_id) with field 406 prefilled; the original is untouched."""
    import uuid as U

    from app.models import DocumentStatus, ESFDocument
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    orig = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    orig_number = orig.esf_number

    r = admin.post(f"/esf/{uuid}/correct")
    new_uuid = r.url.path.split("/")[-1]
    assert new_uuid != uuid
    db_session.expire_all()
    new = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(new_uuid)).one()
    assert new.status == DocumentStatus.DRAFT and new.corrects_id == orig.id
    assert new.supply_info.correction_number == orig_number     # 406 reference prefilled
    # original document is untouched
    orig2 = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    assert orig2.status == DocumentStatus.PUBLISHED and len(orig2.snapshots) == 1
    # correction of an unpublished draft is rejected
    assert admin.post(f"/esf/{new_uuid}/correct").status_code == 409


# ---- immutability -----------------------------------------------------
def test_published_is_readonly(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    assert save(admin, uuid, valid_pairs()).status_code == 409
    assert admin.post(f"/esf/{uuid}/delete").status_code == 409


def test_snapshot_orm_immutable(admin, db_session):
    import uuid as U

    from app.models import ESFDocument
    from app.models.esf_snapshot import SnapshotImmutableError
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    snap = doc.snapshots[0]
    snap.sha256 = "x" * 64
    try:
        db_session.flush()
        assert False, "snapshot update was not blocked"
    except SnapshotImmutableError:
        db_session.rollback()


# ---- PDF --------------------------------------------------------------
def test_pdf_draft_and_published(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    r = admin.get(f"/pdf/{uuid}.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    r = admin.get(f"/pdf/{uuid}.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


# ---- QR ---------------------------------------------------------------
def test_qr_png_and_target(admin):
    from app.services.qr_service import qr_target
    uuid = new_draft(admin)
    r = admin.get(f"/qr/{uuid}.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    # QR encodes the official-format absolute verification URL (matches the reference form)
    assert qr_target(uuid) == f"https://esf.salyk.kg/esf/check-esf?documentUUID={uuid}"


# ---- public verification ---------------------------------------------
def test_public_only_published(admin, anon):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    # draft is NOT public
    assert anon.get(f"/esf/check-esf?documentUUID={uuid}").status_code == 404
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    r = anon.get(f"/esf/check-esf?documentUUID={uuid}")
    assert r.status_code == 200 and "mode-public" in r.text and 'id="esfform"' not in r.text


def test_public_page_is_light_viewer_no_internal_chrome(admin, anon):
    """Public page = light document viewer like the official esf.salyk.kg: a
    centered paper sheet with a minimal LIGHT zoom toolbar, but NO editor /
    workspace chrome and NO owner-only actions."""
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    html = anon.get(f"/esf/check-esf?documentUUID={uuid}").text
    # light viewer + zoom controls present (paper sheet on a canvas)
    assert 'id="viewer-stage"' in html and 'id="viewer-page"' in html and 'id="vb-zoom"' in html
    # NO editor/workspace chrome
    for forbidden in ("esf_workspace.css", "ws-toolbar", 'id="esfform"', 'class="cinp', "edit-bar"):
        assert forbidden not in html, f"public page leaked editor chrome: {forbidden}"
    # NO owner-only actions on the public toolbar
    for owner_only in ("/esf/new", f"/pdf/{uuid}.pdf", "← Назад"):
        assert owner_only not in html, f"public page leaked owner action: {owner_only}"
    # the embedded QR stays inside the document footer
    assert "qr-img" in html and "esf-foot" in html


def test_excel_grid_wired_in_edit_only(admin, anon):
    """v5.0 Module 6: the Excel-grade goods grid (paste range / fill-down /
    arrow nav) is wired in EDIT mode and absent from the public viewer."""
    uuid = new_draft(admin)
    edit = admin.get(f"/esf/{uuid}").text
    assert "Excel-grade goods grid" in edit
    assert "addEventListener('paste'" in edit and "function fillDown()" in edit
    # publish, then the public page must NOT carry the editor grid script
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    pub = anon.get(f"/esf/check-esf?documentUUID={uuid}").text
    assert "Excel-grade goods grid" not in pub and "function fillDown()" not in pub


# ---- autosave ---------------------------------------------------------
def test_autosave_persists_and_blocks_published(admin):
    uuid = new_draft(admin)
    r = admin.post(f"/esf/{uuid}/autosave", content=urlencode(valid_pairs()),
                   headers={**FORM, "X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert "Строительные леса" in admin.get(f"/esf/{uuid}").text
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    r = admin.post(f"/esf/{uuid}/autosave", content=urlencode(valid_pairs()), headers=FORM)
    assert r.status_code == 409 and r.json()["ok"] is False


def test_autosave_requires_login(anon):
    r = anon.post("/esf/00000000-0000-0000-0000-000000000000/autosave",
                  content=urlencode(valid_pairs()), headers=FORM)
    assert r.status_code == 303 and r.headers["location"] == "/login"


# ---- dashboard polish -------------------------------------------------
def test_dashboard_polish_markup(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    body = admin.get("/dashboard").text
    assert 'id="search"' in body and 'id="statusFilter"' in body
    assert 'data-sort=' in body and 'data-status="DRAFT"' in body
    assert "безвозвратно" in body


# ---- Module 35: smart dashboard analytics ---------------------------
def test_dashboard_stats_widgets(admin):
    new_draft(admin)  # at least one draft
    body = admin.get("/dashboard").text
    assert 'class="stats"' in body            # analytics strip
    assert 'class="chart"' in body            # 7-day activity chart
    assert 'data-pick="PUBLISHED"' in body    # click-to-filter stat cards
    assert "Активность · 7 дней" in body


def test_api_esf_pagination_search_sort_filter(admin):
    """v6.1: server-side pagination/search/sort/filter via /api/esf."""
    u = new_draft(admin); save(admin, u, valid_pairs(supplier_name='ООО Зета-Поиск-Юникум'))
    admin.post(f"/esf/{u}/publish", content=urlencode(valid_pairs(supplier_name='ООО Зета-Поиск-Юникум')), headers=FORM)
    new_draft(admin); new_draft(admin)   # a couple of drafts too

    j = admin.get("/api/esf?page=1&page_size=2&sort=created&dir=desc").json()
    assert {"items", "page", "page_size", "total", "total_pages"} <= set(j)
    assert j["page"] == 1 and j["page_size"] == 2 and len(j["items"]) <= 2
    assert j["total"] >= 3 and j["total_pages"] >= 2          # paging engaged

    found = admin.get("/api/esf?q=Зета-Поиск-Юникум").json()["items"]   # server-side search
    assert found and all("Зета-Поиск-Юникум" in it["supplier"] for it in found)

    pub = admin.get("/api/esf?status=PUBLISHED&page_size=100").json()["items"]   # status filter
    assert pub and all(it["status_code"] == "PUBLISHED" for it in pub)

    drafts = admin.get("/api/esf?status=DRAFT&page_size=100").json()["items"]
    assert all(it["status_code"] == "DRAFT" for it in drafts)


def test_batch_publish_and_delete(admin, db_session):
    """v6.0 #3: batch publish publishes editable docs (skips non-editable);
    batch delete removes drafts and skips published."""
    import uuid as U

    from app.models import DocumentStatus, ESFDocument
    a = new_draft(admin); save(admin, a, valid_pairs())
    b = new_draft(admin); save(admin, b, valid_pairs())
    c = new_draft(admin)  # empty draft -> will fail validation on publish

    # batch publish a, b (valid) and c (invalid)
    r = admin.post("/esf/batch/publish", content=urlencode([("uuid", a), ("uuid", b), ("uuid", c)]), headers=FORM)
    assert r.status_code == 200
    db_session.expire_all()
    da = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(a)).one()
    dc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(c)).one()
    assert da.status == DocumentStatus.PUBLISHED and len(da.snapshots) == 1  # published atomically
    assert dc.status == DocumentStatus.DRAFT                                 # invalid -> stayed draft

    # batch delete: a is published (skip), c is a draft (delete)
    admin.post("/esf/batch/delete", content=urlencode([("uuid", a), ("uuid", c)]), headers=FORM)
    db_session.expire_all()
    assert db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(c)).one_or_none() is None
    assert db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(a)).one().status == DocumentStatus.PUBLISHED


def test_batch_pdf_returns_zip(admin):
    a = new_draft(admin); save(admin, a, valid_pairs())
    b = new_draft(admin); save(admin, b, valid_pairs())
    r = admin.post("/esf/batch/pdf", content=urlencode([("uuid", a), ("uuid", b)]), headers=FORM)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(z.namelist()) == 2 and all(n.endswith(".pdf") for n in z.namelist())


def test_dashboard_has_batch_controls(admin):
    new_draft(admin)
    body = admin.get("/dashboard").text
    assert 'id="selectAll"' in body and 'class="rowcheck"' in body and 'id="batchbar"' in body


def test_dashboard_renders_server_side_pagination(admin):
    for _ in range(3):
        new_draft(admin)
    body = admin.get("/dashboard?page_size=2").text
    assert 'class="pager"' in body and 'method="get"' in body   # server-side toolbar + pager
    assert "/api/esf" not in body                                # page is server-rendered, not client-fetched


def test_dashboard_stats_counts(admin, db_session):
    from app.models import User
    from app.services.esf_service import ESFService
    user = db_session.query(User).filter_by(username="t_admin").one()
    before = ESFService(db_session).dashboard_stats(user)
    new_draft(admin)
    after = ESFService(db_session).dashboard_stats(user)
    assert after["total"] == before["total"] + 1
    assert after["drafts"] == before["drafts"] + 1
    assert after["today"] >= 1
    assert len(after["week"]) == 7 and after["week_max"] >= 1


# ---- CSRF -------------------------------------------------------------
def test_csrf_required_on_post(override_db, seed_users):
    c = TestClient(app)  # raw login: no CSRF default header
    c.post("/login", data={"username": "t_admin", "password": "pw"})
    uuid = c.get("/esf/new").url.path.split("/")[-1]
    # POST save with neither header nor csrf_token field -> 403
    r = c.post(f"/esf/{uuid}/save", content=urlencode(valid_pairs()), headers=FORM)
    assert r.status_code == 403


# ---- login rate limiting ---------------------------------------------
def test_login_rate_limit(override_db, seed_users):
    c = TestClient(app)
    for _ in range(5):
        assert c.post("/login", data={"username": "t_admin", "password": "WRONG"}).status_code == 401
    # 6th attempt locked; correct password also locked during the window
    assert c.post("/login", data={"username": "t_admin", "password": "WRONG"}).status_code == 429
    assert c.post("/login", data={"username": "t_admin", "password": "pw"}).status_code == 429


# ---- audit logging ----------------------------------------------------
def test_audit_records_critical_actions(admin, db_session):
    from app.models import AuditLog
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    actions = {a.action for a in db_session.query(AuditLog).all()}
    assert {"LOGIN", "CREATE", "PUBLISH"} <= actions
    assert admin.get("/admin/audit").status_code == 200


# ---- newly-persisted fields ------------------------------------------
def test_new_fields_persist(admin):
    uuid = new_draft(admin)
    pairs = valid_pairs() + [
        ("supplier_branch_inn", "12345678901234"),
        ("supplier_tax_office_code", "004"),
        ("item_customs", "ГТД-777"),
    ]
    save(admin, uuid, pairs)
    body = admin.get(f"/esf/{uuid}").text
    assert "12345678901234" in body and "ГТД-777" in body and 'value="004"' in body


# ---- counterparty lookup (Sprint UX-2) -------------------------------
def test_counterparty_search_requires_auth(anon):
    r = anon.get("/api/counterparties/search?q=016")
    assert r.status_code in (303, 401)   # no public access to the directory


def test_counterparty_upsert_on_save_and_search(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())     # supplier 01610201710254 / 'ООО "Ава Тур"', buyer 6686063027
    by_inn = admin.get("/api/counterparties/search?q=01610201710254").json()["results"]
    assert any(c["inn"] == "01610201710254" for c in by_inn)
    assert by_inn and by_inn[0]["inn"] == "01610201710254"   # exact INN ranked first
    by_name = admin.get("/api/counterparties/search?q=Ава").json()["results"]
    assert any("Ава" in (c["name"] or "") for c in by_name)
    by_buyer = admin.get("/api/counterparties/search?q=6686063027").json()["results"]
    assert any(c["inn"] == "6686063027" for c in by_buyer)
    # autofill payload carries all directory fields
    hit = [c for c in by_inn if c["inn"] == "01610201710254"][0]
    for f in ("inn", "name", "branch", "address", "tax_office", "bank", "bik", "account"):
        assert f in hit


def test_counterparty_search_limit_and_empty(admin):
    assert admin.get("/api/counterparties/search?q=").json()["results"] == []
    assert len(admin.get("/api/counterparties/search?q=zzz_no_match_zzz").json()["results"]) == 0


# ---- recent counterparties (Module 32 right panel) -------------------
def test_counterparty_recent_requires_auth(anon):
    r = anon.get("/api/counterparties/recent")
    assert r.status_code in (303, 401)   # no public access to the directory


def test_counterparty_recent_after_save(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())     # upserts supplier + buyer into the directory
    recent = admin.get("/api/counterparties/recent").json()["results"]
    inns = {c["inn"] for c in recent}
    assert "01610201710254" in inns and "6686063027" in inns


# ---- Module 32: fullscreen editor workspace -------------------------
def test_edit_workspace_chrome_present(admin):
    uuid = new_draft(admin)
    html = admin.get(f"/esf/{uuid}").text
    # workspace stylesheet + all required chrome
    assert "esf_workspace.css" in html
    for marker in ('class="ws"', "ws-toolbar", "ws-left", "ws-right",
                   "ws-status", "ws-canvas", 'id="ws-fs"', 'id="ws-nav"',
                   'id="ws-recent"', "ws-st-section"):
        assert marker in html, marker
    # section anchors used by the left nav
    for sec in ("sec-supplier", "sec-buyer", "sec-supply", "sec-goods", "sec-totals"):
        assert sec in html, sec


def test_workspace_chrome_absent_in_other_modes(admin, anon):
    """The workspace chrome and stylesheet must NOT leak into view / public / pdf —
    those modes stay visually identical."""
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    # owner view of the published doc (mode=view, read-only)
    view = admin.get(f"/esf/{uuid}").text
    assert "esf_workspace.css" not in view and 'class="ws"' not in view
    # public verification page (mode=public)
    public = anon.get(f"/esf/check-esf?documentUUID={uuid}").text
    assert "esf_workspace.css" not in public and "ws-toolbar" not in public


# ---- Module 33: editor productivity (live calc, palette, smart table) ----
def test_editor_productivity_hooks_present(admin):
    uuid = new_draft(admin)
    html = admin.get(f"/esf/{uuid}").text
    # live-calc target cells + productivity engine present (edit mode only)
    for marker in ("calc-amount", "calc-total", "calc-sheet-total",
                   "calc-cur-total", "Module 33", "cmdk", "esfRecalc",
                   "esfNewRow", "esf_draft_"):
        assert marker in html, marker


def test_productivity_hooks_absent_in_public(admin, anon):
    """calc-* are inert class names that may render in all modes, but the
    productivity JS/command-palette must never reach the public page."""
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    public = anon.get(f"/esf/check-esf?documentUUID={uuid}").text
    assert "Module 33" not in public and "cmdk" not in public and "esfRecalc" not in public


def test_totals_match_live_formula(admin):
    """Server totals (the source of truth) match the client live-calc formula:
    amount = price*qty, total = amount+vat+nsp, currency = grand/rate."""
    uuid = new_draft(admin)
    pairs = [(k, v) for (k, v) in valid_pairs()
             if not k.startswith("item_")] + [
        ("item_name", "A"), ("item_unit", "шт"), ("item_price", "116.49"),
        ("item_qty", "21000"), ("item_vat_amount", "0"), ("item_nsp", "0"),
    ]
    save(admin, uuid, pairs)
    html = admin.get(f"/esf/{uuid}").text
    import re
    m = re.search(r'calc-sheet-total">([\d.]+)', html)
    assert m and m.group(1) == "2446290.00"   # 116.49 * 21000


# ---- Module 34: smart goods catalog ---------------------------------
def test_goods_search_requires_auth(anon):
    assert anon.get("/api/goods/search?q=лес").status_code in (303, 401)
    assert anon.get("/api/goods/recent").status_code in (303, 401)


def test_goods_upsert_on_save_and_search(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())     # item "Строительные леса", unit Килограмм
    by_name = admin.get("/api/goods/search?q=Строит").json()["results"]
    assert any("Строительные" in (g["name"] or "") for g in by_name)
    hit = by_name[0]
    for f in ("id", "code", "name", "unit", "price", "vat_rate", "use_count", "is_favorite"):
        assert f in hit
    assert hit["use_count"] >= 1


def test_goods_use_count_increments(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    first = admin.get("/api/goods/search?q=Строит").json()["results"][0]["use_count"]
    save(admin, uuid, valid_pairs())     # save again → same good upserted
    second = admin.get("/api/goods/search?q=Строит").json()["results"][0]["use_count"]
    assert second > first


def test_goods_recent_and_empty(admin):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    recent = admin.get("/api/goods/recent").json()["results"]
    assert any("Строительные" in (g["name"] or "") for g in recent)
    assert admin.get("/api/goods/search?q=").json()["results"] == []


def test_goods_autocomplete_in_editor_only(admin, anon):
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    edit = admin.get(f"/esf/{uuid}").text
    assert "goods-dd" in edit and "/api/goods/search" in edit and 'id="ws-goods"' in edit
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    public = anon.get(f"/esf/check-esf?documentUUID={uuid}").text
    assert "goods-dd" not in public and "/api/goods/search" not in public


# ---- H1: per-user directory isolation --------------------------------
def test_counterparty_directory_isolated_per_user(admin, issuer):
    """A counterparty saved by one user must not surface in another user's lookup."""
    ua = new_draft(admin)
    save(admin, ua, valid_pairs())            # admin upserts supplier 01610201710254
    # issuer must not see admin's directory entries
    assert issuer.get("/api/counterparties/search?q=01610201710254").json()["results"] == []
    assert all("Ава" not in (c.get("name") or "")
               for c in issuer.get("/api/counterparties/search?q=Ава").json()["results"])
    assert issuer.get("/api/counterparties/recent").json()["results"] == []
    # admin still sees their own
    assert any(c["inn"] == "01610201710254"
               for c in admin.get("/api/counterparties/search?q=01610201710254").json()["results"])


def test_goods_directory_isolated_per_user(admin, issuer):
    ua = new_draft(admin)
    save(admin, ua, valid_pairs())            # admin upserts good "Строительные леса"
    assert issuer.get("/api/goods/search?q=Строит").json()["results"] == []
    assert issuer.get("/api/goods/recent").json()["results"] == []
    assert any("Строительные" in (g.get("name") or "")
               for g in admin.get("/api/goods/search?q=Строит").json()["results"])


# ---- C1: stored-XSS hardening ----------------------------------------
def test_esf_number_rejects_markup(admin):
    """User-supplied ESF numbers are restricted to digits/hyphens, blocking the
    inline-handler XSS vector; a well-formed number is still accepted."""
    uuid = new_draft(admin)
    bad = save(admin, uuid, valid_pairs() + [("esf_number", "');alert(1);('")])
    assert bad.status_code == 400
    ok = save(admin, uuid, valid_pairs() + [("esf_number", "0002026-004-00000009")])
    assert ok.status_code in (200, 303)


def test_confirm_handlers_have_no_inline_number(admin):
    """Delete/cancel confirmations read the number from a data-* attribute rather
    than interpolating it into an inline onsubmit handler."""
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    dash = admin.get("/dashboard").text
    assert 'data-confirm="delete"' in dash
    assert "onsubmit=\"return confirm('Удалить документ" not in dash
    admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    view = admin.get(f"/esf/{uuid}").text
    assert 'data-confirm="cancel"' in view
    assert "onsubmit=\"return confirm('Аннулировать" not in view


def test_directory_dropdowns_use_textcontent(admin):
    """The counterparty/goods lookup dropdowns build rows with textContent, not
    innerHTML fed with directory data (stored-XSS fix)."""
    uuid = new_draft(admin)
    html = admin.get(f"/esf/{uuid}").text
    assert "cpName.textContent" in html and "gName.textContent" in html
    assert '<span class="cp-inn">\' + (cp.inn' not in html


# ---- H4/M: infrastructure & config hardening -------------------------
def test_security_headers_present(admin):
    """Every response carries CSP + anti-clickjacking / MIME-sniffing headers."""
    r = admin.get("/dashboard")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_environment_is_production_by_default():
    """Safe-by-default: only the explicit 'development' disables prod hardening."""
    from app.core.config import Settings
    s = Settings()
    for prod in ("production", "prod", "", "staging", "Production"):
        s.ENVIRONMENT = prod
        assert s.is_production, prod
    for dev in ("development", "Development", " development "):
        s.ENVIRONMENT = dev
        assert not s.is_production, dev


def test_secret_key_fail_closed_in_production():
    """Placeholder / empty / short secrets are rejected when ENVIRONMENT=production."""
    from app.core.config import DEFAULT_SECRET, Settings
    s = Settings()
    s.ENVIRONMENT = "production"
    for bad in ("", DEFAULT_SECRET, "CHANGE_ME_64_hex_chars",
                "change-me-to-a-long-random-string", "tooshort"):
        s.SECRET_KEY = bad
        with pytest.raises(RuntimeError):
            s.validate_for_runtime()
    s.SECRET_KEY = "a" * 40                 # long, non-placeholder
    s.validate_for_runtime()                # must not raise
    s.ENVIRONMENT = "development"           # dev never validates the secret
    s.SECRET_KEY = ""
    s.validate_for_runtime()


def test_client_ip_trusts_x_real_ip_only_behind_proxy(monkeypatch):
    """X-Real-IP is honoured only when TRUST_PROXY is set; otherwise the socket peer."""
    from app.core import observability
    from app.core.config import settings

    def req(xri, peer):
        return type("R", (), {
            "headers": {"x-real-ip": xri} if xri else {},
            "client": type("C", (), {"host": peer})(),
        })()

    monkeypatch.setattr(settings, "TRUST_PROXY", False)
    assert observability.client_ip(req("1.2.3.4", "10.0.0.1")) == "10.0.0.1"
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    assert observability.client_ip(req("1.2.3.4", "10.0.0.1")) == "1.2.3.4"
    assert observability.client_ip(req(None, "10.0.0.1")) == "10.0.0.1"


def test_delete_draft_persists_and_cancelled_blocked(admin):
    """Deleting an editable draft persists (single-delete now commits); a CANCELLED
    document (with its immutable snapshot) is rejected with 409, not a 500."""
    uuid = new_draft(admin)
    r = admin.post(f"/esf/{uuid}/delete")
    assert r.status_code in (200, 303)
    assert admin.get(f"/esf/{uuid}").status_code == 404          # actually gone
    # publish -> cancel -> a CANCELLED doc keeps its snapshot and cannot be deleted
    uuid2 = new_draft(admin)
    save(admin, uuid2, valid_pairs())
    admin.post(f"/esf/{uuid2}/publish", content=urlencode(valid_pairs()), headers=FORM)
    admin.post(f"/esf/{uuid2}/cancel")
    resp = admin.post(f"/esf/{uuid2}/delete")
    assert resp.status_code == 409
    assert admin.get(f"/esf/{uuid2}").status_code == 200         # still present


# ---- H2: concurrency-safe publish + atomic ESF-number allocation -----
def test_esf_number_allocation_is_unique_and_monotonic(admin, db_session):
    """Numbers come from a DB sequence: each call is unique and increasing (no
    count()+1 TOCTOU that could hand two publishes the same number)."""
    import re as _re

    from app.services.esf_service import ESFService
    svc = ESFService(db_session)
    nums = [svc.next_esf_number() for _ in range(5)]
    assert len(set(nums)) == 5
    for n in nums:
        assert _re.match(r"^000\d{4}-004-\d{8}$", n), n
    suffixes = [int(n.split("-")[2]) for n in nums]
    assert suffixes == sorted(suffixes) and len(set(suffixes)) == 5


def test_second_publish_creates_no_second_snapshot(admin, db_session):
    """Re-publishing an already-PUBLISHED doc is rejected under the row lock and
    never adds a duplicate snapshot (the double-publish race invariant)."""
    import uuid as U

    from app.models import ESFDocument
    uuid = new_draft(admin)
    save(admin, uuid, valid_pairs())
    r1 = admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    assert r1.status_code in (200, 303)
    doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    assert len(doc.snapshots) == 1
    number_after_first = doc.esf_number
    # second publish: save() re-checks status under the lock -> 409, no mutation
    r2 = admin.post(f"/esf/{uuid}/publish", content=urlencode(valid_pairs()), headers=FORM)
    assert r2.status_code == 409
    db_session.expire_all()
    doc2 = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(uuid)).one()
    assert len(doc2.snapshots) == 1               # still exactly one
    assert doc2.esf_number == number_after_first  # number unchanged (not nulled/reassigned)


# ---- H3: DB-level immutability (snapshots + audit log) ----------------
def test_immutability_triggers_installed(db_session):
    from sqlalchemy import text
    rows = db_session.execute(text(
        "SELECT tgrelid::regclass::text AS tbl FROM pg_trigger "
        "WHERE tgname IN ('esf_snapshots_no_update_delete', 'audit_logs_no_tamper')"
    )).all()
    tables = {r[0] for r in rows}
    assert "esf_snapshots" in tables and "audit_logs" in tables


def test_snapshot_immutable_at_db_level():
    """Raw UPDATE/DELETE (which bypass the ORM events) are blocked by the trigger."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session as _S

    from app.db.session import engine
    from app.models import DocumentStatus, ESFDocument, ESFSnapshot, User
    conn = engine.connect()
    sess = _S(bind=conn)
    try:
        u = User(username="h3_snap_user", hashed_password="x", is_admin=False, is_active=True)
        sess.add(u); sess.flush()
        d = ESFDocument(owner_id=u.id, status=DocumentStatus.PUBLISHED)
        sess.add(d); sess.flush()
        s = ESFSnapshot(document_id=d.id, payload_json={"k": "v"}, sha256="abc")
        sess.add(s); sess.flush()
        sid = s.id
        sess.expunge_all()   # detach so raw SQL below isn't intercepted by the ORM
        for stmt in (text("UPDATE esf_snapshots SET sha256 = 'z' WHERE id = :i"),
                     text("DELETE FROM esf_snapshots WHERE id = :i")):
            sp = sess.begin_nested()
            with pytest.raises(Exception):
                sess.execute(stmt, {"i": sid})
            sp.rollback()
    finally:
        sess.rollback(); sess.close(); conn.close()


def test_audit_log_append_only_at_db_level():
    """Audit content is immutable and rows cannot be deleted, but the FK-cascade
    SET NULL (document_id/user_id) that a legitimate delete triggers is allowed."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session as _S

    from app.db.session import engine
    from app.models import AuditLog
    conn = engine.connect()
    sess = _S(bind=conn)
    try:
        a = AuditLog(action="LOGIN", ip_address="1.1.1.1")
        sess.add(a); sess.flush()
        aid = a.id
        sess.expunge_all()
        sp = sess.begin_nested()
        with pytest.raises(Exception):                          # content change blocked
            sess.execute(text("UPDATE audit_logs SET action = 'HACKED' WHERE id = :i"), {"i": aid})
        sp.rollback()
        sp = sess.begin_nested()
        with pytest.raises(Exception):                          # delete blocked
            sess.execute(text("DELETE FROM audit_logs WHERE id = :i"), {"i": aid})
        sp.rollback()
        sp = sess.begin_nested()
        sess.execute(text("UPDATE audit_logs SET document_id = NULL WHERE id = :i"), {"i": aid})
        sp.rollback()                                           # FK-cascade allowed (no raise)
    finally:
        sess.rollback(); sess.close(); conn.close()


def test_serialize_published_detects_tampered_snapshot(db_session):
    """serialize_published re-verifies the sha256 and fails closed on a mismatch."""
    from fastapi import HTTPException

    from app.models import DocumentStatus, ESFDocument, User
    from app.models.esf_snapshot import ESFSnapshot
    from app.services import snapshot_service
    from app.services.esf_service import ESFService
    u = User(username="h3_tamper_user", hashed_password="x", is_admin=False, is_active=True)
    db_session.add(u); db_session.flush()
    d = ESFDocument(owner_id=u.id, status=DocumentStatus.PUBLISHED)
    db_session.add(d); db_session.flush()
    good = ESFSnapshot(document_id=d.id, payload_json={"a": 1},
                       sha256=snapshot_service.content_hash({"a": 1}))
    db_session.add(good); db_session.flush()
    svc = ESFService(db_session)
    assert svc.serialize_published(d) == {"a": 1}          # valid snapshot returns payload
    bad = ESFSnapshot(document_id=d.id, payload_json={"a": 2}, sha256="deadbeef")
    db_session.add(bad); db_session.flush()                # newer -> becomes latest_snapshot
    with pytest.raises(HTTPException):
        svc.serialize_published(d)


# ---- M10: validation rules (buyer INN, foreign-currency rate, VAT base) ----
def test_validation_new_rules(admin, db_session):
    import uuid as U

    from app.models import ESFDocument
    from app.services.validation_service import validate_document

    def errs_for(pairs):
        u = new_draft(admin)
        save(admin, u, pairs)
        doc = db_session.query(ESFDocument).filter(ESFDocument.uuid == U.UUID(u)).one()
        return validate_document(doc)

    def over(pairs, **repl):
        return [(k, repl.get(k, v)) for (k, v) in pairs]

    # a fully-consistent document passes (guards the happy path / no false positives)
    assert errs_for(valid_pairs()) == []
    # buyer INN with letters -> rejected (symmetric with the supplier check)
    assert any("ИНН покупателя должен содержать только цифры" in e
               for e in errs_for(over(valid_pairs(), buyer_inn="AB12")))
    # foreign currency (643) without an exchange rate -> rejected
    assert any("иностранной валюты необходимо указать курс" in e
               for e in errs_for(over(valid_pairs(), currency_rate="")))
    # VAT that does not match rate x base (12% declared, 0 entered) -> rejected
    assert any("не соответствует ставке" in e
               for e in errs_for(over(valid_pairs(), item_vat_rate="12", item_vat_amount="0")))
    # negative VAT -> rejected
    assert any("сумма НДС не может быть отрицательной" in e
               for e in errs_for(over(valid_pairs(), item_vat_rate="0", item_vat_amount="-5")))
