"""Cross-database compatible column types.

Provides a GUID type that uses PostgreSQL's native UUID on Postgres
and stores as CHAR(32) on other databases (SQLite, MySQL).
This allows the same ORM models to work in production (Postgres)
and tests (SQLite) without modification.
"""

import uuid

from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise stores
    as a 32-character hex string (CHAR(32)).

    Usage:
        id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    """

    impl = String(32)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        else:
            # Store as 32-char hex string for SQLite/MySQL
            if isinstance(value, uuid.UUID):
                return value.hex
            else:
                return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
