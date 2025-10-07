import logging
from typing import Optional, Generator
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import QueuePool
import time

logger = logging.getLogger(__name__)

# Global variables for database components
engine = None
SessionLocal = None
DATABASE_AVAILABLE = False

def init_database():
    """Initialize MySQL database connection"""
    global engine, SessionLocal, DATABASE_AVAILABLE
    
    try:
        from app.models.base import Base
        from app.config import settings
        
        # Get database URL from settings
        database_url = settings.database_url
        connect_args = settings.database_connect_args
        
        logger.info(f"🔌 Connecting to database: {settings.DATABASE_TYPE}")
        logger.info(f"📍 Host: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}")
        logger.info(f"🗄️ Database: {settings.DATABASE_NAME}")
        
        # Create engine with connection pooling
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=QueuePool,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,  # Verify connections before use
            echo=False  # Set to True for SQL debugging
        )
        
        # Test database connection
        _test_database_connection(engine)

        # Ensure existing schema has required columns before ORM mapping
        _ensure_schema_compatibility(engine)
        
        # Create SessionLocal class
        SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=engine,
            expire_on_commit=False
        )
        
        # Import all models to ensure they're registered (in correct order)
        from app.models.website import Website
        from app.models.user import User
        from app.models.file_metadata import FileMetadata
        from app.models.user_file_access import UserFileAccess
        from app.models.query_log import QueryLog
        from app.models.chat_tracking import ChatSession, ChatQuery
        from app.models.collection import Collection, CollectionUser
        from app.models.system_prompt import SystemPrompt
        from app.models.vector_database import VectorDatabase
        from app.models.activity_log import ActivityLog
        from app.models.activity_stats import ActivityStats
        
        # Configure mappers to ensure relationships are properly set up
        from sqlalchemy.orm import configure_mappers
        try:
            configure_mappers()
            logger.info("✅ SQLAlchemy mappers configured successfully")
        except Exception as e:
            logger.warning(f"⚠️ Mapper configuration warning: {e}")
            # Continue anyway - this might not be critical
        
        # Create all tables
        logger.info("📋 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        DATABASE_AVAILABLE = True
        logger.info("✅ Database initialized successfully")
        
        # Log database info
        _log_database_info()
        
    except ImportError as e:
        logger.error(f"❌ Required database modules not available: {e}")
        raise RuntimeError(f"Database initialization failed: Missing dependencies - {e}")
        
    except OperationalError as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise RuntimeError(f"Database connection failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise RuntimeError(f"Database initialization failed: {e}")

def _test_database_connection(engine):
    """Test database connection"""
    try:
        with engine.connect() as connection:
            # Test basic connectivity
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            logger.info("🔗 Database connection test successful")
            
            # Test database exists and is accessible
            if engine.url.drivername.startswith('mysql'):
                result = connection.execute(text("SELECT DATABASE()"))
                db_name = result.fetchone()[0]
                logger.info(f"📊 Connected to database: {db_name}")
                
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        raise

def _log_database_info():
    """Log database configuration information"""
    from app.config import settings
    
    logger.info("📋 Database Configuration:")
    logger.info(f"   Type: {settings.DATABASE_TYPE}")
    logger.info(f"   Host: {settings.DATABASE_HOST}")
    logger.info(f"   Port: {settings.DATABASE_PORT}")
    logger.info(f"   Database: {settings.DATABASE_NAME}")
    logger.info(f"   User: {settings.DATABASE_USER}")
    logger.info(f"   Charset: {settings.DATABASE_CHARSET}")
    logger.info(f"   Pool Size: {settings.DATABASE_POOL_SIZE}")
    logger.info(f"   Max Overflow: {settings.DATABASE_MAX_OVERFLOW}")
    logger.info(f"   SSL Disabled: {settings.DATABASE_SSL_DISABLED}")


def _ensure_schema_compatibility(engine):
    """Ensure legacy databases have required schema columns"""
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        if "websites" in tables:
            _sync_websites_table(engine, inspector)

        if "collections" in tables:
            _sync_collections_table(engine, inspector)

        if "users" in tables:
            _sync_users_table(engine, inspector)

        if "vector_databases" in tables:
            _sync_vector_databases_table(engine, inspector)

        if "chat_sessions" in tables:
            _sync_chat_sessions_table(engine, inspector)

        if "chat_queries" in tables:
            _sync_chat_queries_table(engine, inspector)

    except Exception as schema_error:
        logger.error(f"❌ Failed to synchronize database schema: {schema_error}")
        raise


def _sync_websites_table(engine, inspector):
    existing_columns = {column["name"] for column in inspector.get_columns("websites")}

    alterations = []
    if "max_users" not in existing_columns:
        alterations.append("ADD COLUMN max_users INT NOT NULL DEFAULT 100")
    if "max_files" not in existing_columns:
        alterations.append("ADD COLUMN max_files INT NOT NULL DEFAULT 1000")
    if "max_storage_mb" not in existing_columns:
        alterations.append("ADD COLUMN max_storage_mb INT NOT NULL DEFAULT 10240")
    if "logo_url" not in existing_columns:
        alterations.append("ADD COLUMN logo_url VARCHAR(500) NULL")
    if "primary_color" not in existing_columns:
        alterations.append("ADD COLUMN primary_color VARCHAR(7) NOT NULL DEFAULT '#6366f1'")
    if "secondary_color" not in existing_columns:
        alterations.append("ADD COLUMN secondary_color VARCHAR(7) NOT NULL DEFAULT '#8b5cf6'")
    if "custom_css" not in existing_columns:
        alterations.append("ADD COLUMN custom_css TEXT NULL")
    if "admin_email" not in existing_columns:
        alterations.append("ADD COLUMN admin_email VARCHAR(255) NULL")
    if "contact_phone" not in existing_columns:
        alterations.append("ADD COLUMN contact_phone VARCHAR(50) NULL")
    if "created_at" not in existing_columns:
        alterations.append("ADD COLUMN created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP")
    if "updated_at" not in existing_columns:
        alterations.append("ADD COLUMN updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

    if alterations:
        logger.info("🛠️ Updating legacy 'websites' table with missing columns")
        alter_statement = "ALTER TABLE websites " + ", ".join(alterations)
        with engine.begin() as connection:
            connection.execute(text(alter_statement))
        logger.info("✅ 'websites' table schema synchronized")


def _sync_collections_table(engine, inspector):
    columns = inspector.get_columns("collections")
    existing_columns = {column["name"] for column in columns}
    column_map = {column["name"]: column for column in columns}

    alterations = []
    if "description" not in existing_columns:
        alterations.append("ADD COLUMN description TEXT NULL")
    if "website_id" not in existing_columns:
        alterations.append("ADD COLUMN website_id VARCHAR(36) NULL")
    else:
        website_col = column_map.get("website_id")
        if website_col and not website_col.get("nullable", True):
            alterations.append("MODIFY COLUMN website_id VARCHAR(36) NULL")
    if "website_url" not in existing_columns:
        alterations.append("ADD COLUMN website_url VARCHAR(500) NULL")
    if "vector_db_id" not in existing_columns:
        alterations.append("ADD COLUMN vector_db_id VARCHAR(36) NULL")
    else:
        vector_col = column_map.get("vector_db_id")
        if vector_col and not vector_col.get("nullable", True):
            alterations.append("MODIFY COLUMN vector_db_id VARCHAR(36) NULL")
    if "admin_user_id" not in existing_columns:
        alterations.append("ADD COLUMN admin_user_id VARCHAR(36) NULL")
    if "admin_email" not in existing_columns:
        alterations.append("ADD COLUMN admin_email VARCHAR(255) NULL")
    if "is_active" not in existing_columns:
        alterations.append("ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1")
    if "created_at" not in existing_columns:
        alterations.append("ADD COLUMN created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP")
    if "updated_at" not in existing_columns:
        alterations.append("ADD COLUMN updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

    if alterations:
        logger.info("🛠️ Updating legacy 'collections' table with missing columns")
        alter_statement = "ALTER TABLE collections " + ", ".join(alterations)
        with engine.begin() as connection:
            connection.execute(text(alter_statement))
        logger.info("✅ 'collections' table schema synchronized")


def _sync_users_table(engine, inspector):
    existing_columns = inspector.get_columns("users")
    column_map = {column["name"]: column for column in existing_columns}

    alterations = []

    email_column = column_map.get("email")
    if email_column and not email_column.get("nullable", True):
        alterations.append("MODIFY COLUMN email VARCHAR(255) NULL")

    if alterations:
        logger.info("🛠️ Updating legacy 'users' table with optional fields")
        alter_statement = "ALTER TABLE users " + ", ".join(alterations)
        with engine.begin() as connection:
            connection.execute(text(alter_statement))
        logger.info("✅ 'users' table schema synchronized")


def _sync_vector_databases_table(engine, inspector):
    existing_columns = inspector.get_columns("vector_databases")
    column_map = {column["name"]: column for column in existing_columns}

    alterations = []

    website_column = column_map.get("website_id")
    if website_column and not website_column.get("nullable", True):
        alterations.append("MODIFY COLUMN website_id VARCHAR(36) NULL")

    if alterations:
        logger.info("🛠️ Updating legacy 'vector_databases' table with optional fields")
        alter_statement = "ALTER TABLE vector_databases " + ", ".join(alterations)
        with engine.begin() as connection:
            connection.execute(text(alter_statement))
        logger.info("✅ 'vector_databases' table schema synchronized")


def _sync_chat_sessions_table(engine, inspector):
    existing_columns = inspector.get_columns("chat_sessions")
    column_map = {column["name"]: column for column in existing_columns}

    alterations = []

    if "collection_id" not in column_map:
        alterations.append("ADD COLUMN collection_id VARCHAR(50) NULL")

    if alterations:
        logger.info("🛠️ Updating legacy 'chat_sessions' table with collection support")
        alter_statement = "ALTER TABLE chat_sessions " + ", ".join(alterations)
        with engine.begin() as connection:
            connection.execute(text(alter_statement))
        logger.info("✅ 'chat_sessions' table schema synchronized")


def _sync_chat_queries_table(engine, inspector):
    existing_columns = inspector.get_columns("chat_queries")
    column_map = {column["name"]: column for column in existing_columns}

    alterations = []

    if "collection_id" not in column_map:
        alterations.append("ADD COLUMN collection_id VARCHAR(50) NULL")

    if alterations:
        logger.info("🛠️ Updating legacy 'chat_queries' table with collection support")
        alter_statement = "ALTER TABLE chat_queries " + ", ".join(alterations)
        with engine.begin() as connection:
            connection.execute(text(alter_statement))
        logger.info("✅ 'chat_queries' table schema synchronized")


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    if not DATABASE_AVAILABLE or not SessionLocal:
        raise RuntimeError("Database is not available. Please check your database configuration.")
    
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_db_health() -> dict:
    """Check database health and return status"""
    if not DATABASE_AVAILABLE or not SessionLocal:
        return {
            "status": "unhealthy", 
            "database": "disconnected", 
            "error": "Database not initialized"
        }
    
    try:
        db = SessionLocal()
        try:
            # Test basic connectivity
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            
            # Get database info
            from app.config import settings
            db_info = {
                "status": "healthy",
                "database": "connected",
                "type": settings.DATABASE_TYPE,
                "host": settings.DATABASE_HOST,
                "port": settings.DATABASE_PORT,
                "database": settings.DATABASE_NAME,
                "pool_size": settings.DATABASE_POOL_SIZE,
                "charset": settings.DATABASE_CHARSET
            }
            
            # Get additional MySQL-specific info
            if settings.DATABASE_TYPE.lower() == "mysql":
                try:
                    result = db.execute(text("SELECT VERSION()"))
                    version = result.fetchone()[0]
                    db_info["version"] = version
                    
                    result = db.execute(text("SELECT DATABASE()"))
                    current_db = result.fetchone()[0]
                    db_info["current_database"] = current_db
                    
                except Exception as e:
                    logger.warning(f"Could not get MySQL version info: {e}")
            
            return db_info
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected", 
            "error": str(e)
        }

def create_database_if_not_exists():
    """Create database if it doesn't exist (MySQL only)"""
    from app.config import settings
    
    if settings.DATABASE_TYPE.lower() != "mysql":
        return
    
    try:
        # Connect without specifying database
        temp_url = f"mysql+pymysql://{settings.DATABASE_USER}"
        if settings.DATABASE_PASSWORD:
            temp_url += f":{settings.DATABASE_PASSWORD}"
        temp_url += f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}"
        temp_url += f"?charset={settings.DATABASE_CHARSET}"
        
        temp_engine = create_engine(temp_url)
        
        with temp_engine.connect() as connection:
            # Check if database exists
            result = connection.execute(
                text("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :db_name"),
                {"db_name": settings.DATABASE_NAME}
            )
            
            if not result.fetchone():
                # Create database
                logger.info(f"📋 Creating database: {settings.DATABASE_NAME}")
                connection.execute(text(f"CREATE DATABASE {settings.DATABASE_NAME} CHARACTER SET {settings.DATABASE_CHARSET} COLLATE {settings.DATABASE_COLLATION}"))
                connection.commit()
                logger.info(f"✅ Database {settings.DATABASE_NAME} created successfully")
            else:
                logger.info(f"📋 Database {settings.DATABASE_NAME} already exists")
        
        temp_engine.dispose()
        
    except Exception as e:
        logger.error(f"❌ Failed to create database: {e}")
        raise

def get_database_stats() -> dict:
    """Get database statistics"""
    if not DATABASE_AVAILABLE or not SessionLocal:
        return {"error": "Database not available"}
    
    try:
        db = SessionLocal()
        try:
            from app.config import settings
            stats = {}
            
            if settings.DATABASE_TYPE.lower() == "mysql":
                # Get table statistics
                result = db.execute(text("""
                    SELECT 
                        table_name,
                        table_rows,
                        data_length,
                        index_length
                    FROM information_schema.tables 
                    WHERE table_schema = :db_name
                """), {"db_name": settings.DATABASE_NAME})
                
                tables = []
                total_rows = 0
                total_size = 0
                
                for row in result:
                    table_info = {
                        "name": row[0],
                        "rows": row[1] or 0,
                        "data_size": row[2] or 0,
                        "index_size": row[3] or 0
                    }
                    tables.append(table_info)
                    total_rows += table_info["rows"]
                    total_size += table_info["data_size"] + table_info["index_size"]
                
                stats = {
                    "tables": tables,
                    "total_rows": total_rows,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2)
                }
            
            return stats
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {"error": str(e)}
