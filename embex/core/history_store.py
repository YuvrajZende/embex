"""
HistoryStore — SQLite-based version history for tracked files.
Stores full file snapshots so users can view and restore previous versions.
"""

import hashlib
import sqlite3
import time
from pathlib import Path


# SQL to create the database tables
SCHEMA_SQL = """
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

CREATE TABLE IF NOT EXISTS embed_checksums (
    file_path   TEXT    PRIMARY KEY,
    checksum    TEXT    NOT NULL,
    embedded_at INTEGER NOT NULL
);
"""


def _checksum(content):
    """Calculate SHA-256 checksum of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class HistoryStore:
    """Manages file version snapshots in a local SQLite database."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

        # Add folder column if it doesn't exist (for older databases)
        try:
            self.conn.execute(
                "ALTER TABLE embed_checksums ADD COLUMN folder TEXT NOT NULL DEFAULT '.'"
            )
            self.conn.commit()
        except Exception:
            pass  # column already exists

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def snapshot_file(self, file_path, content, language="unknown", folder=".", message=None):
        """Save a new version of a file. Skips if content hasn't changed.
        Returns the version number.
        """
        cs = _checksum(content)
        now = int(time.time())
        cur = self.conn.cursor()

        # Check if we already track this file
        cur.execute(
            "SELECT current_version FROM file_registry WHERE file_path = ?",
            (file_path,),
        )
        row = cur.fetchone()

        if row is not None:
            current_version = row["current_version"]
            # Check if content actually changed
            cur.execute(
                "SELECT checksum FROM snapshots WHERE file_path = ? AND version = ?",
                (file_path, current_version),
            )
            snap = cur.fetchone()
            if snap and snap["checksum"] == cs:
                return current_version  # no change

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
        self.conn.commit()
        return new_version

    def get_file_history(self, file_path):
        """Get all version metadata for a file (newest first)."""
        cur = self.conn.execute(
            "SELECT version, timestamp, checksum, message FROM snapshots WHERE file_path = ? ORDER BY version DESC",
            (file_path,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_snapshot(self, file_path, version):
        """Get the content of a specific version. Returns None if not found."""
        cur = self.conn.execute(
            "SELECT content FROM snapshots WHERE file_path = ? AND version = ?",
            (file_path, version),
        )
        row = cur.fetchone()
        return row["content"] if row else None

    def get_latest_version(self, file_path):
        """Get the current version number (0 if file is not tracked)."""
        cur = self.conn.execute(
            "SELECT current_version FROM file_registry WHERE file_path = ?",
            (file_path,),
        )
        row = cur.fetchone()
        return row["current_version"] if row else 0

    def get_latest_content(self, file_path):
        """Get the content of the latest version. Returns None if not tracked."""
        version = self.get_latest_version(file_path)
        if version == 0:
            return None
        return self.get_snapshot(file_path, version)

    def restore_to_version(self, file_path, version):
        """Set the current version pointer to a specific version (used after restore).
        Returns True on success, False if version doesn't exist.
        """
        cur = self.conn.cursor()
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
        self.conn.commit()
        return True

    def list_all_files(self):
        """Get all tracked file paths."""
        cur = self.conn.execute("SELECT file_path FROM file_registry ORDER BY file_path")
        return [row["file_path"] for row in cur.fetchall()]

    def list_files_in_folder(self, folder_prefix):
        """Get all file paths that start with the given folder prefix."""
        prefix = folder_prefix.rstrip("/") + "/"
        cur = self.conn.execute(
            "SELECT file_path FROM file_registry WHERE file_path LIKE ? ORDER BY file_path",
            (prefix + "%",),
        )
        return [row["file_path"] for row in cur.fetchall()]

    def get_embed_checksum(self, file_path):
        """Get the checksum of the last embedded version. Returns None if never embedded."""
        cur = self.conn.execute(
            "SELECT checksum FROM embed_checksums WHERE file_path = ?",
            (file_path,),
        )
        row = cur.fetchone()
        return row["checksum"] if row else None

    def set_embed_checksum(self, file_path, checksum, folder="."):
        """Record the checksum of the version just embedded."""
        now = int(time.time())
        self.conn.execute(
            "INSERT INTO embed_checksums (file_path, checksum, embedded_at, folder) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(file_path) DO UPDATE SET checksum = excluded.checksum, "
            "embedded_at = excluded.embedded_at, folder = excluded.folder",
            (file_path, checksum, now, folder),
        )
        self.conn.commit()

    def get_all_embed_paths(self):
        """Get all (file_path, folder) pairs that have been embedded."""
        cur = self.conn.execute(
            "SELECT file_path, folder FROM embed_checksums ORDER BY file_path"
        )
        return [(row["file_path"], row["folder"]) for row in cur.fetchall()]

    def delete_embed_checksum(self, file_path):
        """Remove the embed record for a file (when it's deleted)."""
        self.conn.execute(
            "DELETE FROM embed_checksums WHERE file_path = ?", (file_path,)
        )
        self.conn.commit()
