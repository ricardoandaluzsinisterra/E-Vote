import os
import time
import logging
import psycopg

logger = logging.getLogger(__name__)
logging.basicConfig(filename='myapp.log', level=logging.INFO)

class DatabaseManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.connection = None
            cls._instance.cursor = None
        return cls._instance
    
    def __init__(self):
        """Initialize DatabaseManager with empty connection and cursor."""
        # Only initialize if not already initialized
        if not hasattr(self, '_initialized'):
            self.connection = None
            self.cursor = None
            self._initialized = True
        
    def connect(self, max_retries=3):
        """
        Establish database connection with retry logic.
        
        Args:
            max_retries (int): Maximum number of connection attempts (default: 3)
            
        Returns:
            psycopg.Connection: Database connection object
            
        Raises:
            psycopg.Error: If all connection attempts fail
        """
        # Retry logic
        for attempt in range(max_retries):
            # Database connection through psycopg
            try:
                conn = psycopg.connect(
                    host=os.environ['DB_HOST'],
                    port=5432,
                    user='postgres',
                    password='password',
                    dbname='user_info_db'
                )
                logger.info("Database connection successful")
                
                self.connection = conn
            
                self.connection.autocommit = True
                self.cursor = self.connection.cursor()
                
                return conn
                
            except psycopg.Error as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt + 1 == max_retries:
                    logger.error("Max connection retries reached")
                    raise
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
        Create the database tables if they don't exist.
        Creates users, polls, poll_options, and votes tables with proper constraints.

        Raises:
            RuntimeError: If cursor is not available (connect() not called)
        """
        if self.cursor is None:
            raise RuntimeError("Database cursor not available. Ensure connect() is called first.")

        # Enable UUID extension
        self.cursor.execute("""
            CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        """)

        # Create users table
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

        # Create polls table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                title VARCHAR(500) NOT NULL,
                description TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                CONSTRAINT fk_polls_created_by FOREIGN KEY (created_by)
                    REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT chk_expires_after_created CHECK (expires_at IS NULL OR expires_at > created_at)
            );

            CREATE INDEX IF NOT EXISTS idx_polls_created_by ON polls(created_by);
            CREATE INDEX IF NOT EXISTS idx_polls_is_active ON polls(is_active);
        """)

        # Create poll_options table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS poll_options (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                poll_id UUID NOT NULL,
                option_text VARCHAR(500) NOT NULL,
                vote_count INTEGER DEFAULT 0,
                display_order INTEGER DEFAULT 0,
                CONSTRAINT fk_poll_options_poll_id FOREIGN KEY (poll_id)
                    REFERENCES polls(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_poll_options_poll_id ON poll_options(poll_id);
        """)

        # Create votes table with UUID, constraints, and indexes
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id INTEGER NOT NULL,
                poll_id UUID NOT NULL,
                option_id UUID NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_votes_user_id FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_votes_poll_id FOREIGN KEY (poll_id)
                    REFERENCES polls(id) ON DELETE CASCADE,
                CONSTRAINT fk_votes_option_id FOREIGN KEY (option_id)
                    REFERENCES poll_options(id) ON DELETE CASCADE,
                CONSTRAINT unique_user_poll UNIQUE (user_id, poll_id)
            );

            CREATE INDEX IF NOT EXISTS idx_votes_user_id ON votes(user_id);
            CREATE INDEX IF NOT EXISTS idx_votes_poll_id ON votes(poll_id);
        """)

# FastAPI dependency for database access
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
