# test_db.py - Test database connection
from sqlalchemy import create_engine, text
from app.config import settings

print('Testing SQLAlchemy database connection...')
print('Connection details:')
print('  Host:', settings.DATABASE_HOST)
print('  Port:', settings.DATABASE_PORT)
print('  User:', settings.DATABASE_USER)
print('  Database:', settings.DATABASE_NAME)
password_display = '*' * len(settings.DATABASE_PASSWORD) if settings.DATABASE_PASSWORD else '(empty)'
print('  Password:', password_display)
print('  URL:', settings.database_url)

try:
    # Create engine
    engine = create_engine(settings.database_url)

    # Test connection
    with engine.connect() as connection:
        result = connection.execute(text('SELECT 1'))
        print('✅ Database connection successful')

        # Check tables
        result = connection.execute(text('SHOW TABLES'))
        tables = result.fetchall()
        print(f'✅ Found {len(tables)} tables:')
        for table in tables:
            print(f'   - {table[0]}')

        # Check if users table exists
        result = connection.execute(text("SHOW TABLES LIKE 'users'"))
        users_table = result.fetchone()
        if users_table:
            print('✅ Users table exists')
            result = connection.execute(text('SELECT COUNT(*) FROM users'))
            count = result.fetchone()[0]
            print(f'✅ Users table has {count} records')

            # Show users
            result = connection.execute(text('SELECT username, role, is_active FROM users'))
            users = result.fetchall()
            print('Users in database:')
            for user in users:
                print(f'   - {user[0]} (role: {user[1]}, active: {user[2]})')
        else:
            print('❌ Users table does not exist')

    engine.dispose()

except Exception as e:
    print(f'❌ Database connection failed: {e}')
    import traceback
    traceback.print_exc()
