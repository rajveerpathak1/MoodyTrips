import os
from urllib.parse import quote_plus
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

def get_db_url(use_default_db=False):
    """
    Constructs the PostgreSQL connection URL.
    If use_default_db is True, it connects to 'postgres' database instead of 'moody_trips',
    which is useful for verifying/creating the database initially.
    """
    database_url = os.getenv("DATABASE_URL")
    
    # If DATABASE_URL is set in environment, use it
    if database_url and not use_default_db:
        if "sslmode=" not in database_url:
            separator = "&" if "?" in database_url else "?"
            database_url = f"{database_url}{separator}sslmode=require"
        return database_url

    # Fallback to individual connection parameters (with defaults provided by user)
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "751829@Taru")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = "postgres" if use_default_db else os.getenv("DB_NAME", "moody_trips")

    escaped_password = quote_plus(password)
    url = f"postgresql://{user}:{escaped_password}@{host}:{port}/{dbname}"
    return url

def get_db_connection(use_default_db=False):
    url = get_db_url(use_default_db=use_default_db)
    conn = psycopg.connect(
        url,
        autocommit=True,
        row_factory=dict_row
    )
    return conn

def init_db():
    """
    Automatically initializes the database and creates the required tables.
    """
    # 1. Connect to default postgres DB and ensure moody_trips exists
    try:
        dbname = os.getenv("DB_NAME", "moody_trips")
        # Check database existence only if we are using custom credentials
        if not os.getenv("DATABASE_URL"):
            with get_db_connection(use_default_db=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
                    if not cur.fetchone():
                        print(f"Database '{dbname}' does not exist. Creating...")
                        # Terminate active connections if any (should be none since it doesn't exist)
                        cur.execute(f"CREATE DATABASE {dbname}")
                        print(f"Database '{dbname}' created successfully.")
    except Exception as e:
        print("Warning during database creation check:", e)

    # 2. Connect to moody_trips DB and create tables
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print("Initializing database tables...")
            
            # Create Users Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create User Chats / Threads Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_chats (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    thread_id VARCHAR(255) UNIQUE NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create Chat Messages Table (stores history for display)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    thread_id VARCHAR(255) REFERENCES user_chats(thread_id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            print("Database tables initialized successfully.")

# =====================================================================
# Database Helpers
# =====================================================================

def create_user(email: str, password_hash: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
                (email.lower().strip(), password_hash)
            )
            return cur.fetchone()

def get_user_by_email(email: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
            return cur.fetchone()

def get_user_by_id(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, created_at FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()

def create_chat(user_id: int, thread_id: str, title: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_chats (user_id, thread_id, title) VALUES (%s, %s, %s) RETURNING *",
                (user_id, thread_id, title)
            )
            return cur.fetchone()

def get_user_chats(user_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM user_chats WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            return cur.fetchall()

def update_chat_title(thread_id: str, title: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_chats SET title = %s WHERE thread_id = %s RETURNING *",
                (title, thread_id)
            )
            return cur.fetchone()

def save_chat_message(thread_id: str, role: str, content: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (thread_id, role, content) VALUES (%s, %s, %s) RETURNING *",
                (thread_id, role, content)
            )
            return cur.fetchone()

def get_chat_messages(thread_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, created_at FROM chat_messages WHERE thread_id = %s ORDER BY created_at ASC",
                (thread_id,)
            )
            return cur.fetchall()
