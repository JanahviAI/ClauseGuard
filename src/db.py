import sqlite3
import os
import sys

def init_db(db_path="data/db/portfolio.db"):
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    
    cursor = conn.cursor()
    
    # 1. Services table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT
        )
    """)
    
    # 2. Canonical Entities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canonical_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    
    # 3. Clauses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clauses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            severity_score REAL,
            specificity_score REAL,
            risk_category TEXT,
            recipients_json TEXT,
            entity_specificity TEXT,
            retention_raw TEXT,
            retention_days REAL,
            purposes_json TEXT,
            confidence REAL,
            evidence TEXT,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)

    # Backward-compatible migration for older DB files.
    cursor.execute("PRAGMA table_info(clauses)")
    clause_columns = {row[1] for row in cursor.fetchall()}
    missing_columns = {
        "recipients_json": "TEXT",
        "entity_specificity": "TEXT",
        "retention_raw": "TEXT",
        "retention_days": "REAL",
        "purposes_json": "TEXT",
        "confidence": "REAL",
        "evidence": "TEXT",
    }
    for column_name, column_type in missing_columns.items():
        if column_name not in clause_columns:
            cursor.execute(
                f"ALTER TABLE clauses ADD COLUMN {column_name} {column_type}"
            )
    
    # 4. Clause to Entity Mapping table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clause_entity_mapping (
            clause_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            PRIMARY KEY (clause_id, entity_id),
            FOREIGN KEY (clause_id) REFERENCES clauses(id) ON DELETE CASCADE,
            FOREIGN KEY (entity_id) REFERENCES canonical_entities(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database successfully initialized at {db_path}")

if __name__ == "__main__":
    # Determine absolute path to ensure we run from project root context
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_file_path = os.path.join(base_dir, 'data', 'db', 'portfolio.db')
    init_db(db_file_path)
