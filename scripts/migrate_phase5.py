import sqlite3

def run_migration():
    conn = sqlite3.connect('database/smart_learning.db')
    cursor = conn.cursor()

    def get_columns(table):
        cursor.execute(f"PRAGMA table_info({table})")
        return [col[1] for col in cursor.fetchall()]

    # 1. Update classrooms
    c_cols = get_columns('classrooms')
    if 'status' not in c_cols:
        cursor.execute("ALTER TABLE classrooms ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL")
        print('Added status to classrooms')
    if 'is_archived' not in c_cols:
        cursor.execute("ALTER TABLE classrooms ADD COLUMN is_archived BOOLEAN DEFAULT 0 NOT NULL")
        print('Added is_archived to classrooms')
    if 'max_students' not in c_cols:
        cursor.execute("ALTER TABLE classrooms ADD COLUMN max_students INTEGER DEFAULT 50 NOT NULL")
        print('Added max_students to classrooms')

    # 2. Update classroom_members unique index
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_classroom_member ON classroom_members(classroom_id, student_id)")
    print('Ensured unique index uq_classroom_member')

    # 3. Update assignments
    a_cols = get_columns('assignments')
    if 'description' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN description TEXT")
        print('Added description to assignments')
    if 'open_date' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN open_date DATETIME")
        print('Added open_date to assignments')
    if 'max_attempts' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN max_attempts INTEGER DEFAULT 1 NOT NULL")
        print('Added max_attempts to assignments')
    if 'allow_late_submission' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN allow_late_submission BOOLEAN DEFAULT 0 NOT NULL")
        print('Added allow_late_submission to assignments')
    if 'allow_review' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN allow_review BOOLEAN DEFAULT 1 NOT NULL")
        print('Added allow_review to assignments')
    if 'status' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN status VARCHAR(20) DEFAULT 'DRAFT' NOT NULL")
        print('Added status to assignments')
    if 'is_published' not in a_cols:
        cursor.execute("ALTER TABLE assignments ADD COLUMN is_published BOOLEAN DEFAULT 0 NOT NULL")
        print('Added is_published to assignments')

    # 4. Update exam_attempts
    ea_cols = get_columns('exam_attempts')
    if 'assignment_id' not in ea_cols:
        cursor.execute("ALTER TABLE exam_attempts ADD COLUMN assignment_id VARCHAR(36)")
        print('Added assignment_id to exam_attempts')
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_exam_attempts_assignment_id ON exam_attempts(assignment_id)")
    print('Ensured index ix_exam_attempts_assignment_id')

    conn.commit()
    conn.close()
    print("Phase 5 DB Migration completed successfully.")

if __name__ == '__main__':
    run_migration()
