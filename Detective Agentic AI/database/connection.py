"""
database/connection.py

SQLite connection management, DDL schema initialization, and migration helpers.
Ensures thread safety, foreign key integrity, and WAL concurrency.
"""

import json
import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "investigation.db")
CASES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cases"))


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    target_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Create all relational tables if they do not exist."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                case_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                location TEXT DEFAULT 'Not provided',
                date_opened TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                assigned_investigator TEXT DEFAULT 'Unassigned',
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                extra_metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
            CREATE INDEX IF NOT EXISTS idx_cases_priority ON cases(priority);
            CREATE INDEX IF NOT EXISTS idx_cases_date_opened ON cases(date_opened);

            CREATE TABLE IF NOT EXISTS suspects (
                suspect_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                alias TEXT DEFAULT 'Not provided',
                age TEXT DEFAULT 'Not provided',
                location TEXT DEFAULT 'Not provided',
                known_associations TEXT DEFAULT 'Not provided',
                observed_behaviors TEXT DEFAULT 'Not provided',
                modus_operandi TEXT DEFAULT 'Not provided',
                traits TEXT DEFAULT '[]',
                case_connections TEXT DEFAULT '[]',
                notes TEXT DEFAULT '',
                evidence_links TEXT DEFAULT '[]',
                assessment_history TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                source TEXT DEFAULT 'Field Officer',
                uploaded_by TEXT DEFAULT 'System',
                timestamp TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                file_size_bytes INTEGER DEFAULT 0,
                storage_path TEXT DEFAULT '',
                status TEXT DEFAULT 'VERIFIED',
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence(sha256_hash);

            CREATE TABLE IF NOT EXISTS timeline_events (
                event_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT DEFAULT 'Investigation Unit',
                linked_evidence_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_timeline_case ON timeline_events(case_id);

            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                target_object TEXT DEFAULT '',
                result TEXT DEFAULT 'SUCCESS',
                details TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);

            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """)
        logger.info("Database schema initialized successfully.")
    finally:
        conn.close()


def migrate_existing_cases(db_path: Optional[str] = None, cases_dir: Optional[str] = None) -> int:
    """
    Import existing cases from cases/*.json into SQLite database.
    Idempotent: skips cases that already exist in the database.
    Does not delete or alter any JSON files.
    """
    init_db(db_path)
    target_dir = cases_dir or CASES_DIR
    if not os.path.isdir(target_dir):
        return 0

    conn = get_db_connection(db_path)
    imported = 0
    try:
        existing_ids = {row[0] for row in conn.execute("SELECT case_id FROM cases;").fetchall()}
        
        for fname in sorted(os.listdir(target_dir)):
            if not fname.lower().endswith(".json") or fname.lower().startswith(("package", "config", "skills-lock", ".")):
                continue
            fpath = os.path.join(target_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not data.get("case_id"):
                    continue

                case_id = str(data.get("case_id")).strip()

                title = str(data.get("title") or data.get("case_title") or f"Case {case_id}").strip()
                case_type = str(data.get("crime_type") or data.get("case_type") or "General Investigation").strip()
                desc = str(data.get("summary") or data.get("description") or "").strip()
                loc = str(data.get("location") or "Not provided").strip()
                date_opened = str(data.get("date_opened") or data.get("created_at") or "2026-01-01").split()[0]
                status = str(data.get("status") or "OPEN").upper().strip()
                priority = str(data.get("priority") or "MEDIUM").upper().strip()
                investigator = str(data.get("assigned_investigator") or "Detective Unit").strip()
                
                tags = data.get("tags") or data.get("common_traits") or []
                if not isinstance(tags, list):
                    tags = [str(tags)]
                
                # Extra metadata
                extra = {}
                for k in (
                    "modus_operandi", "common_traits", "evidence", "suspects",
                    "case_notes", "personality_disorder", "court_or_authority",
                    "legal_citation", "judgment_date", "source", "source_url",
                    "ipc_sections"
                ):
                    if k in data:
                        extra[k] = data[k]

                conn.execute("""
                    INSERT OR REPLACE INTO cases (
                        case_id, title, case_type, description, location,
                        date_opened, status, priority, assigned_investigator,
                        tags, created_at, updated_at, extra_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?);
                """, (
                    case_id, title, case_type, desc, loc,
                    date_opened, status, priority, investigator,
                    json.dumps(tags), json.dumps(extra)
                ))
                if case_id not in existing_ids:
                    existing_ids.add(case_id)
                    imported += 1
            except Exception as e:
                logger.warning("Failed to migrate case %s: %s", fname, e)
        conn.commit()
    finally:
        conn.close()
    logger.info("Migrated %d existing JSON case(s) into database.", imported)
    return imported
