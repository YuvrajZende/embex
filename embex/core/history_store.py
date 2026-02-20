"""
HistoryStore — SQLite-backed version history for every tracked file.

Stores full file snapshots so users can view logs, diffs, and restore
previous versions.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT    NOT NULL,
    version     INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    timestamp   INTEGER NOT NULL,
    checksum    TEXT    NOT NULL,
    message     TEXT    DEFAULT NULL,
    UNIQUE(file_path, version)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_file ON snapshots(file_path);

CREATE TABLE IF NOT EXISTS file_registry (
    file_path       TEXT    PRIMARY KEY,
    current_version INTEGER NOT NULL DEFAULT 0,
    first_seen      INTEGER NOT NULL,
    last_modified   INTEGER NOT NULL,
    language        TEXT,
    folder          TEXT
);

CREATE TABLE IF NOT EXISTS project_meta (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS embed_checksums (
    file_path   TEXT    PRIMARY KEY,
    checksum    TEXT    NOT NULL,
    embedded_at INTEGER NOT NULL
);
"""


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class HistoryStore:
    """Manage file version snapshots in a local SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Snapshot operations
    # ------------------------------------------------------------------

    def snapshot_file(
        self,
        file_path: str,
        content: str,
        language: str = "unknown",
        folder: str = ".",
        message: str | None = None,
    ) -> int:
        """Save a new version snapshot for *file_path*.

        Skips the snapshot if the content is identical to the latest version
        (same checksum).

        Returns
        -------
        int
            The version number of the new (or existing) snapshot.
        """
        cs = _checksum(content)
        now = int(time.time())
        cur = self._conn.cursor()

        # Check if file is already registered
        cur.execute(
            "SELECT current_version FROM file_registry WHERE file_path = ?",
            (file_path,),
        )
        row = cur.fetchone()

        if row is not None:
            current_version = row["current_version"]
            # Check if content is unchanged
            cur.execute(
                "SELECT checksum FROM snapshots WHERE file_path = ? AND version = ?",
                (file_path, current_version),
            )
            snap = cur.fetchone()
            if snap and snap["checksum"] == cs:
                return current_version  # unchanged

            new_version = current_version + 1
            cur.execute(
                "UPDATE file_registry SET current_version = ?, last_modified = ? WHERE file_path = ?",
                (new_version, now, file_path),
            )
        else:
            new_version = 1
            cur.execute(
                "INSERT INTO file_registry (file_path, current_version, first_seen, last_modified, language, folder) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (file_path, new_version, now, now, language, folder),
            )

        cur.execute(
            "INSERT INTO snapshots (file_path, version, content, timestamp, checksum, message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_path, new_version, content, now, cs, message),
        )
        self._conn.commit()
        return new_version

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_file_history(self, file_path: str) -> list[dict[str, Any]]:
        """Return all version metadata for a file (newest first)."""
        cur = self._conn.execute(
            "SELECT version, timestamp, checksum, message FROM snapshots WHERE file_path = ? ORDER BY version DESC",
            (file_path,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_snapshot(self, file_path: str, version: int) -> str | None:
        """Return the content of a specific version, or ``None``."""
        cur = self._conn.execute(
            "SELECT content FROM snapshots WHERE file_path = ? AND version = ?",
            (file_path, version),
        )
        row = cur.fetchone()
        return row["content"] if row else None

    def get_latest_version(self, file_path: str) -> int:
        """Return the current version number (0 if file is untracked)."""
        cur = self._conn.execute(
            "SELECT current_version FROM file_registry WHERE file_path = ?",
            (file_path,),
        )
        row = cur.fetchone()
        return row["current_version"] if row else 0

    def get_latest_content(self, file_path: str) -> str | None:
        """Return the content of the latest snapshot, or ``None``."""
        version = self.get_latest_version(file_path)
        if version == 0:
            return None
        return self.get_snapshot(file_path, version)

    def restore_to_version(self, file_path: str, version: int) -> bool:
        """Reset the current version pointer to *version* after a restore.

        This prevents the file watcher from creating a redundant new snapshot
        when it detects the restored file — the checksum will match the now-
        current version and ``snapshot_file`` will skip it.

        Returns ``True`` on success, ``False`` if the version does not exist.
        """
        cur = self._conn.cursor()
        cur.execute(
            "SELECT 1 FROM snapshots WHERE file_path = ? AND version = ?",
            (file_path, version),
        )
        if cur.fetchone() is None:
            return False

        now = int(time.time())
        cur.execute(
            "UPDATE file_registry SET current_version = ?, last_modified = ? WHERE file_path = ?",
            (version, now, file_path),
        )
        self._conn.commit()
        return True

    # ------------------------------------------------------------------
    # Folder / bulk query helpers
    # ------------------------------------------------------------------

    def list_all_files(self) -> list[str]:
        """Return every file path that has at least one snapshot."""
        cur = self._conn.execute("SELECT file_path FROM file_registry ORDER BY file_path")
        return [row["file_path"] for row in cur.fetchall()]

    def list_files_in_folder(self, folder_prefix: str) -> list[str]:
        """Return all tracked file paths whose path starts with *folder_prefix*.

        *folder_prefix* should use forward-slashes and should NOT end with one
        (e.g. ``"src/auth"``).  The comparison is case-sensitive.
        """
        # Normalise: strip trailing slash so LIKE pattern is consistent.
        prefix = folder_prefix.rstrip("/") + "/"
        cur = self._conn.execute(
            "SELECT file_path FROM file_registry WHERE file_path LIKE ? ORDER BY file_path",
            (prefix + "%",),
        )
        return [row["file_path"] for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Embed-checksum cache (independent of history snapshots)
    # ------------------------------------------------------------------

    def get_embed_checksum(self, file_path: str) -> str | None:
        """Return the SHA-256 checksum of the last successfully embedded
        version of *file_path*, or ``None`` if the file has never been
        embedded.
        """
        cur = self._conn.execute(
            "SELECT checksum FROM embed_checksums WHERE file_path = ?",
            (file_path,),
        )
        row = cur.fetchone()
        return row["checksum"] if row else None

    def set_embed_checksum(self, file_path: str, checksum: str) -> None:
        """Record *checksum* as the digest of the version that was just
        embedded for *file_path*.
        """
        now = int(time.time())
        self._conn.execute(
            "INSERT INTO embed_checksums (file_path, checksum, embedded_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(file_path) DO UPDATE SET checksum = excluded.checksum, "
            "embedded_at = excluded.embedded_at",
            (file_path, checksum, now),
        )
        self._conn.commit()
