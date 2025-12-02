import os
import time
import logging
import psycopg
import redis

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.connection = None
            cls._instance.cursor = None
            cls._instance.redis_client = None
        return cls._instance
    
    def __init__(self):
        """Initialize DatabaseManager with empty connection, cursor and optional redis client."""
        # Only initialize if not already initialized
        if not hasattr(self, '_initialized'):
            self.connection = None
            self.cursor = None
            self.redis_client = None
            self._initialized = True
        
    def connect(self, max_retries=3):
        """
        Establish database connection with retry logic and initialize Redis client if configured.
        
        Args:
            max_retries (int): Maximum number of connection attempts (default: 3)
            
        Returns:
            psycopg.Connection: Database connection object
            
        Raises:
            psycopg.Error: If all connection attempts fail
        """
        # Retry logic for Postgres
        for attempt in range(max_retries):
            try:
                conn = psycopg.connect(
                    host=os.environ.get("DB_HOST", "localhost"),
                    port=int(os.environ.get("DB_PORT", 5432)),
                    user=os.environ.get("DB_USER", "postgres"),
                    password=os.environ.get("DB_PASSWORD", "postgres"),
                    dbname=os.environ.get("DB_NAME", "user_info_db")
                )
                logger.info(
                    "Database connection successful to %s:%s",
                    os.environ.get("DB_HOST", "localhost"),
                    os.environ.get("DB_PORT", 5432),
                )

                self.connection = conn
                # Ensure autocommit is set
                self.connection.autocommit = True
                self.cursor = self.connection.cursor()

                # Initialize Redis client if configured via env
                redis_host = os.environ.get("REDIS_HOST")
                if redis_host:
                    try:
                        redis_port = int(os.environ.get("REDIS_PORT", 6379))
                        redis_db = int(os.environ.get("REDIS_DB", 0))
                        client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
                        client.ping()
                        self.redis_client = client
                        logger.info("Redis connection successful to %s:%s db=%s", redis_host, redis_port, redis_db)
                    except Exception as e:
                        logger.warning("Redis initialization failed: %s", e)
                        self.redis_client = None

                return conn

            except psycopg.Error as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt + 1 == max_retries:
                    logger.error("Max connection retries reached for Postgres")
                    raise
                # Exponential backoff
                time.sleep(2 ** attempt)
            
    def get_cursor(self):
        """
        Get the current database cursor.
        
        Returns:
            psycopg.Cursor: Database cursor for executing queries
        """
        return self.cursor
    
    def get_connection(self):
        """
        Create a new DatabaseManager instance and establish connection.
        
        Returns:
            psycopg.Connection: New database connection
        """
        db = DatabaseManager()
        conn = db.connect()
        return conn
        
    def initialize_tables(self):
        """
        Create the users, polls, poll_options, and votes tables if they don't exist.

        Raises:
            RuntimeError: If cursor is not available (connect() not called)
        """
        if self.cursor is None:
            raise RuntimeError("Database cursor not available. Ensure connect() is called first.")

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_token VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title VARCHAR(255) NOT NULL,
                description TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE,
                CONSTRAINT fk_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT check_expires_after_created CHECK (expires_at IS NULL OR expires_at > created_at)
            );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                poll_id UUID NOT NULL,
                option_text VARCHAR(500) NOT NULL,
                vote_count INTEGER DEFAULT 0,
                display_order INTEGER NOT NULL,
                CONSTRAINT fk_poll FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
            );
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id INTEGER NOT NULL,
                poll_id UUID NOT NULL,
                option_id UUID NOT NULL,
                voted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT unique_user_poll UNIQUE (user_id, poll_id),
                CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_poll_vote FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
                CONSTRAINT fk_option FOREIGN KEY (option_id) REFERENCES poll_options(id) ON DELETE CASCADE
            );
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_polls_created_by_created_at
            ON polls(created_by, created_at DESC);
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_polls_is_active_created_at
            ON polls(is_active, created_at DESC);
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_poll_options_poll_id_display_order
            ON poll_options(poll_id, display_order);
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_votes_poll_id ON votes(poll_id);
        """)

# FastAPI dependency for database access (internal to db_ops_service)
def get_database() -> DatabaseManager:
    """
    FastAPI dependency that provides access to the singleton DatabaseManager.
    
    Returns:
        DatabaseManager: The singleton database manager instance
    """
    db = DatabaseManager()
    if db.cursor is None:
        raise RuntimeError("Database not connected. Ensure startup event has run.")
    return db
