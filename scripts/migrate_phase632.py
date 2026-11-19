"""
Migration script for Phase 6.3.2 Exam Engine Hardening:
1. Reconciles any duplicate records in student_answers(attempt_id, question_id).
2. Adds 'version' column to student_answers if not exists.
3. Creates unique index uq_attempt_question_answer ON student_answers(attempt_id, question_id).
Safe to run idempotently on SQLite and development databases.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "smart_learning.db")

def run_migration():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Reconcile any existing duplicate student_answers
    cursor.execute("""
        SELECT attempt_id, question_id, COUNT(*) as cnt 
        FROM student_answers 
        GROUP BY attempt_id, question_id 
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"Found {len(duplicates)} duplicate (attempt_id, question_id) groups. Reconciling...")
        for att_id, q_id, cnt in duplicates:
            # Keep the row with the most recent answered_at or updated_at, or highest time_spent_seconds
            cursor.execute("""
                SELECT id FROM student_answers 
                WHERE attempt_id = ? AND question_id = ?
                ORDER BY updated_at DESC, answered_at DESC, time_spent_seconds DESC
            """, (att_id, q_id))
            row_ids = [r[0] for r in cursor.fetchall()]
            keep_id = row_ids[0]
            remove_ids = row_ids[1:]
            for rem_id in remove_ids:
                cursor.execute("DELETE FROM student_answers WHERE id = ?", (rem_id,))
            print(f"Reconciled group ({att_id}, {q_id}): kept {keep_id}, removed {len(remove_ids)} duplicates.")
    else:
        print("Zero duplicate student_answers detected. Data integrity clean.")

    # 2. Check and add 'version' column to student_answers
    cursor.execute("PRAGMA table_info(student_answers)")
    columns = [col[1] for col in cursor.fetchall()]
    if "version" not in columns:
        cursor.execute("ALTER TABLE student_answers ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        print("Added column 'version' (INTEGER NOT NULL DEFAULT 1) to student_answers.")
    else:
        print("Column 'version' already exists in student_answers.")

    # 3. Create unique index on (attempt_id, question_id)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_question_answer 
        ON student_answers(attempt_id, question_id)
    """)
    print("Ensured UNIQUE INDEX uq_attempt_question_answer ON student_answers(attempt_id, question_id).")

    conn.commit()
    conn.close()
    print("Phase 6.3.2 migration completed successfully.")

if __name__ == "__main__":
    run_migration()
