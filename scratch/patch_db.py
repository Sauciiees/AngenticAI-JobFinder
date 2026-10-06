import sqlite3

def patch_db():
    try:
        conn = sqlite3.connect('data/jobfinder.db')
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE applications ADD COLUMN logo_url VARCHAR;")
        conn.commit()
        print("Column 'logo_url' added successfully!")
    except sqlite3.OperationalError as e:
        print(f"OperationalError (might already exist): {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    patch_db()
