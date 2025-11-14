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
        Create the users table if it doesn't exist.
        
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
