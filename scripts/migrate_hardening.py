import sqlite3

def run_hardening_migration():
    conn = sqlite3.connect('database/smart_learning.db')
    cursor = conn.cursor()

    def get_columns(table):
        cursor.execute(f"PRAGMA table_info({table})")
        return [col[1] for col in cursor.fetchall()]

    ea_cols = get_columns('exam_attempts')
    if 'answer_key_snapshot_json' not in ea_cols:
        cursor.execute("ALTER TABLE exam_attempts ADD COLUMN answer_key_snapshot_json TEXT")
        print("Added answer_key_snapshot_json to exam_attempts")

    # Partial unique index for active standalone exam attempts
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_exam_attempt 
        ON exam_attempts(student_id, exam_id) 
        WHERE status = 'IN_PROGRESS' AND assignment_id IS NULL
    """)
    print("Ensured partial unique index uq_active_exam_attempt")

    # Partial unique index for active assignment attempts
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_assignment_attempt 
        ON exam_attempts(student_id, assignment_id) 
        WHERE status = 'IN_PROGRESS' AND assignment_id IS NOT NULL
    """)
    print("Ensured partial unique index uq_active_assignment_attempt")

    conn.commit()
    conn.close()
    print("Hardening migration completed successfully.")

if __name__ == '__main__':
    run_hardening_migration()
