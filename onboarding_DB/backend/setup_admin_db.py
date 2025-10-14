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

load_dotenv()

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
        
        # Read and execute schema
        schema_path = os.path.join(os.path.dirname(__file__), 'database_schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        cursor.execute(schema_sql)
        conn.commit()
        
        print("✅ Created tables in onboarding_admin")
        
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
