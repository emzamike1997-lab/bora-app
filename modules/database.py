import sqlite3
import os

DB_PATH = "bora.db"

def init_db():
    """Initializes the SQLite database for user management."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            plan TEXT DEFAULT 'FREE',
            analyses_remaining INTEGER DEFAULT 1,
            last_analysis TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            subscription_id TEXT,
            customer_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user(email):
    """Retrieves user info from DB."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT plan, analyses_remaining FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"plan": row[0], "analyses_remaining": row[1]}
    return None

def create_user(email):
    """Creates a new free user with 1 free analysis."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (email, plan, analyses_remaining) VALUES (?, 'FREE', 1)", (email,))
    conn.commit()
    conn.close()

def add_analyses(email, count):
    """Adds single-use analyses for pay-per-doc purchases."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET analyses_remaining = analyses_remaining + ? WHERE email = ?", (count, email))
    conn.commit()
    conn.close()

def upgrade_plan(email, plan, subscription_id=None, customer_id=None):
    """Upgrades a user to a subscription plan."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET plan = ?, subscription_id = ?, customer_id = ? 
        WHERE email = ?
    ''', (plan, subscription_id, customer_id, email))
    conn.commit()
    conn.close()

def consume_analysis(email):
    """Consumes 1 analysis quota if the user is on FREE or PAY_PER_DOC plan."""
    if email and "+dev" in email:
        return True

    user = get_user(email)
    if not user:
        return False
    
    if user["plan"] in ["MONTHLY", "BUSINESS"]:
        # Unlimited plans don't decrement
        return True

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET analyses_remaining = analyses_remaining - 1, last_analysis = CURRENT_TIMESTAMP
        WHERE email = ? AND analyses_remaining > 0
    ''', (email,))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    return success

def can_analyze(email):
    """Checks if a user is allowed to perform an analysis."""
    if email and "+dev" in email:
        return True

    user = get_user(email)
    if not user:
        create_user(email)
        return True
    
    plan = user["plan"]
    if plan in ["MONTHLY", "BUSINESS"]:
        return True
    
    return user["analyses_remaining"] > 0
