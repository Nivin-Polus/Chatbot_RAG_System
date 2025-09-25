import sqlite3
import os

db_path = 'chatbot_test.db'
if os.path.exists(db_path):
    print(f'Database file exists: {db_path}')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f'Found {len(tables)} tables:')
        for table in tables:
            print(f'   - {table[0]}')

        conn.close()
        print('Database is accessible')
    except Exception as e:
        print(f'Database access failed: {e}')
else:
    print(f'Database file not found: {db_path}')
