#!/usr/bin/env python3
"""
Setup script for admin database
Creates the onboarding_admin database and tables
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import sys
from dotenv import load_dotenv

# Load environment variables from parent directory (onboarding_DB/.env)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

# Get configurable table names
USER_CONNECTIONS_TABLE = os.getenv("USER_CONNECTIONS_TABLE", "db_connection_infos")
AUDIT_LOG_TABLE = os.getenv("AUDIT_LOG_TABLE", "onboarding_audit_log")

def setup_admin_database():
    """Create admin database and tables"""
    
    print("Attempting to create admin database...")
    print()
    
    # Try different connection approaches
    connection_attempts = [
        # Try as postgres superuser first
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': '',
            'database': 'postgres',
            'description': 'postgres superuser (no password)'
        },
        # Try as postgres with common password
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': 'postgres',
            'database': 'postgres',
            'description': 'postgres superuser (password: postgres)'
        },
        # Try as testuser (might work if it has CREATEDB privilege)
        {
            'host': 'localhost',
            'port': 5432,
            'user': 'testuser',
            'password': 'testpass',
            'database': 'postgres',
            'description': 'testuser'
        }
    ]
    
    conn = None
    successful_connection = None
    
    for attempt in connection_attempts:
        try:
            print(f"Trying: {attempt['description']}...")
            conn = psycopg2.connect(
                host=attempt['host'],
                port=attempt['port'],
                user=attempt['user'],
                password=attempt['password'],
                database=attempt['database']
            )
            successful_connection = attempt
            print(f"✅ Connected as {attempt['user']}")
            break
        except Exception as e:
            print(f"   Failed: {e}")
            continue
    
    if not conn:
        print("\n❌ Could not connect to PostgreSQL with any credentials.")
        print("\n📋 To fix this, run one of these commands:")
        print("\n   Option 1 - Grant testuser permission to create databases:")
        print("   psql -U postgres -c \"ALTER USER testuser CREATEDB;\"")
        print("\n   Option 2 - Create the database manually as postgres:")
        print("   psql -U postgres -c \"CREATE DATABASE onboarding_admin OWNER testuser;\"")
        print("\n   Option 3 - Run this script as postgres user:")
        print("   sudo -u postgres python setup_admin_db.py")
        sys.exit(1)
    
    try:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'onboarding_admin'")
        exists = cursor.fetchone()
        
        if not exists:
            try:
                cursor.execute("CREATE DATABASE onboarding_admin")
                print("✅ Created database: onboarding_admin")
            except psycopg2.errors.InsufficientPrivilege:
                print("\n❌ Permission denied to create database")
                print("\n📋 Please run one of these commands as postgres superuser:")
                print("   psql -U postgres -c \"CREATE DATABASE onboarding_admin;\"")
                print("   psql -U postgres -c \"GRANT ALL ON DATABASE onboarding_admin TO testuser;\"")
                sys.exit(1)
        else:
            print("ℹ️  Database onboarding_admin already exists")
        
        # Grant permissions if we connected as superuser
        if successful_connection['user'] == 'postgres':
            try:
                cursor.execute("GRANT ALL PRIVILEGES ON DATABASE onboarding_admin TO testuser")
                print("✅ Granted permissions to testuser")
            except:
                pass
        
        cursor.close()
        conn.close()
        
        # Now connect to the new database and create tables
        # Use testuser credentials for consistency
        print("\nConnecting to onboarding_admin database...")
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='testuser',
            password='testpass',
            database='onboarding_admin'
        )
        
        cursor = conn.cursor()
        
        # Create tables using configurable names
        schema_sql = f"""
-- Admin Database Schema with configurable table names
-- User connections and catalog information
CREATE TABLE IF NOT EXISTS {USER_CONNECTIONS_TABLE} (
    id SERIAL PRIMARY KEY,
    user_email TEXT UNIQUE NOT NULL,
    db_type TEXT NOT NULL DEFAULT 'postgres',
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    db_user TEXT NOT NULL,
    db_password TEXT NOT NULL,  -- In production, encrypt this
    db_name TEXT NOT NULL,
    catalog_markdown TEXT,  -- Store the generated catalog
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_query_at TIMESTAMP,
    status TEXT DEFAULT 'active'
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_{USER_CONNECTIONS_TABLE}_user_email ON {USER_CONNECTIONS_TABLE}(user_email);
CREATE INDEX IF NOT EXISTS idx_{USER_CONNECTIONS_TABLE}_status ON {USER_CONNECTIONS_TABLE}(status);

-- Audit log for tracking
CREATE TABLE IF NOT EXISTS {AUDIT_LOG_TABLE} (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    action TEXT,  -- 'onboard', 'catalog_update', 'query', etc.
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOG_TABLE}_email ON {AUDIT_LOG_TABLE}(user_email);
"""
        
        cursor.execute(schema_sql)
        conn.commit()
        
        print("✅ Created tables in onboarding_admin")
        print(f"   - User connections table: {USER_CONNECTIONS_TABLE}")
        print(f"   - Audit log table: {AUDIT_LOG_TABLE}")
        
        # Grant permissions on tables
        cursor.execute("""
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO testuser;
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO testuser;
        """)
        conn.commit()
        
        # Verify tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print("\n📋 Tables created:")
        for table in tables:
            print(f"   - {table[0]}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Admin database setup complete!")
        print("🔗 Connection string: postgresql://testuser:testpass@localhost:5432/onboarding_admin")
        
    except Exception as e:
        print(f"❌ Error setting up admin database: {e}")
        if conn:
            conn.close()
        raise

if __name__ == "__main__":
    print("🚀 Setting up admin database for onboarding system...")
    print("=" * 60)
    setup_admin_database()
