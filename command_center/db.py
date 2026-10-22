from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .errors import DomainError


class Database:
    def __init__(self, url: str):
        self.url = url

    @contextmanager
    def connect(self):
        if not self.url.startswith(("postgresql://", "postgres://")):
            raise DomainError("DATABASE_NOT_CONFIGURED", 503)
        with psycopg.connect(self.url, row_factory=dict_row, connect_timeout=3,
                            options="-c statement_timeout=10000 -c lock_timeout=5000") as connection:
            yield connection

    def ready(self):
        with self.connect() as c:
            row = c.execute("SELECT version FROM command_center.schema_migrations WHERE version=1").fetchone()
            if not row:
                raise DomainError("MIGRATION_REQUIRED", 503)

    def migrate(self):
        path = Path(__file__).with_name("migrations") / "001_initial.sql"
        body = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(body.encode()).hexdigest()
        with self.connect() as c:
            c.execute("SELECT pg_advisory_xact_lock(8192773401)")
            c.execute("CREATE SCHEMA IF NOT EXISTS command_center")
            c.execute("CREATE TABLE IF NOT EXISTS command_center.schema_migrations(version integer PRIMARY KEY,sha256 text NOT NULL)")
            row = c.execute("SELECT sha256 FROM command_center.schema_migrations WHERE version=1").fetchone()
            if row:
                if row["sha256"] != digest:
                    raise DomainError("MIGRATION_CHECKSUM_MISMATCH", 503)
                return
            c.execute(body)
            c.execute("INSERT INTO command_center.schema_migrations VALUES(1,%s)", (digest,))
