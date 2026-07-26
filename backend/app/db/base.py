"""The single declarative Base for the entire project.

There is exactly ONE Base. Every model inherits from it so that
`Base.metadata` holds the complete schema for Alembic and reflection.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
