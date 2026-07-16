# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Shared SQLite connection ownership for local storage."""

import sqlite3
import threading
from pathlib import Path
from src.core.observability import get_logger

logger = get_logger(__name__)


class StafStore:
    """Owns a single shared SQLite connection for local storage.

    Configures WAL journaling, foreign-key enforcement and a busy
    timeout once, and exposes one reentrant lock so multiple stores
    (``JobStore``, ``ScheduleStore``) can safely share the same
    connection instead of each opening its own.
    """

    def __init__(
        self,
        db_path: Path | str = "data/scheduler.db",
    ) -> None:
        """Initialize the shared database connection.

        :param db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            isolation_level="DEFERRED",
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._closed = False

        logger.info(f"Initialized shared SQLite storage at {self.db_path}")

    @property
    def conn(self) -> sqlite3.Connection:
        """The shared SQLite connection.

        :returns: The underlying ``sqlite3.Connection``.
        """
        return self._conn

    def executescript(self, schema_sql: str) -> None:
        """Run a DDL script against the shared connection.

        :param schema_sql: One or more ``CREATE TABLE``/``CREATE INDEX`` statements.
        """
        with self.lock:
            self._conn.executescript(schema_sql)

    def commit(self) -> None:
        """Commit the current transaction on the shared connection."""
        with self.lock:
            self._conn.commit()

    def rollback(self) -> None:
        """Roll back the current transaction on the shared connection."""
        with self.lock:
            self._conn.rollback()

    def close(self) -> None:
        """Close the shared connection.

        Idempotent: calling this more than once after the connection
        is already closed is a no-op.
        """
        with self.lock:
            if not self._closed:
                self._conn.close()
                self._closed = True
