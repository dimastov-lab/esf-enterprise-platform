from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_production_compose_pins_existing_canonical_roots() -> None:
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    production_env = (ROOT / ".env.production.example").read_text(encoding="utf-8")

    assert compose.startswith("name: esf-enterprise-clean-starter\n")
    assert "  pg_data:\n    name: esf-enterprise-clean-starter_pg_data\n" in compose
    assert "  esf_storage:\n    name: esf-enterprise-clean-starter_esf_storage\n" in compose
    assert "DATABASE_URL: ${DATABASE_URL}" in compose
    assert (
        "DATABASE_URL=postgresql+psycopg2://esf:CHANGE_ME_strong_db_password@db:5432/esf"
        in production_env
    )


def test_development_compose_cannot_create_a_persistent_alternate_root() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "tmpfs:\n      - /var/lib/postgresql/data" in compose
    assert "postgres_data" not in compose


def test_wave0_evidence_records_backup_and_quarantined_root() -> None:
    evidence = (ROOT / "docs" / "WAVE0_DATA_ROOT.md").read_text(encoding="utf-8")

    assert "a5df81ca1175f49f62a1b1c4039c5c5d1df616c6" in evidence
    assert "pre-acceptance-20260808.dump" in evidence
    assert "529aaa6499e83c6ddececbc5a62ccabeff940391f3851b9f9f782a62bfc0e093" in evidence
    assert "esf-enterprise-clean-starter_postgres_data" in evidence
    assert "QUARANTINED / NO-USE" in evidence
