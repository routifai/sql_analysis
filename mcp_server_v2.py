#!/usr/bin/env python3
"""
AnalyticsSQL MCP Server v2 - Database Execution Service
Clean architecture: User's LLM handles text-to-SQL, MCP server handles database operations
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
ADMIN_DB_CONNECTION = os.getenv("ADMIN_DB_CONNECTION", "postgresql://testuser:testpass@localhost:5432/onboarding_admin")
REQUIRE_EMAIL_AUTH = os.getenv("REQUIRE_EMAIL_AUTH", "true").lower() == "true"
DEFAULT_USER_EMAIL = os.getenv("DEFAULT_USER_EMAIL", "")
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "1000"))
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", "30"))

# Database table names (configurable)
USER_CONNECTIONS_TABLE = os.getenv("USER_CONNECTIONS_TABLE", "db_connection_infos")
AUDIT_LOG_TABLE = os.getenv("AUDIT_LOG_TABLE", "onboarding_audit_log")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate configuration
if REQUIRE_EMAIL_AUTH and not ADMIN_DB_CONNECTION:
    logger.error("❌ Missing ADMIN_DB_CONNECTION for email authentication")
    raise ValueError("ADMIN_DB_CONNECTION is required when REQUIRE_EMAIL_AUTH=true")

# Connection pools
admin_db_pool = None
user_db_pools: Dict[str, SimpleConnectionPool] = {}

# Initialize MCP server
app = FastMCP("AnalyticsSQL Database Service")

def get_admin_db_connection():
    """Get connection to admin database"""
    global admin_db_pool
    if not admin_db_pool:
        admin_db_pool = SimpleConnectionPool(1, 5, ADMIN_DB_CONNECTION)
    return admin_db_pool.getconn()

def return_admin_db_connection(conn):
    """Return connection to admin pool"""
    if admin_db_pool:
        admin_db_pool.putconn(conn)

def get_user_info(user_email: str) -> Optional[Dict[str, Any]]:
    """Get user information from admin database"""
    try:
        conn = get_admin_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(f"""
            SELECT *
            FROM {USER_CONNECTIONS_TABLE}
            WHERE user_email = %s AND status = 'active'
        """, (user_email,))
        
        user = cursor.fetchone()
        cursor.close()
        return_admin_db_connection(conn)
        
        return dict(user) if user else None
        
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        return None

def get_user_connection_pool(user_email: str, user_info: Dict[str, Any]) -> Optional[SimpleConnectionPool]:
    """Get or create connection pool for user's database"""
    global user_db_pools
    
    if user_email in user_db_pools:
        return user_db_pools[user_email]
    
    try:
        # Build connection string from user info
        connection_string = (
            f"postgresql://{user_info['db_user']}:{user_info['db_password']}"
            f"@{user_info['host']}:{user_info['port']}/{user_info['db_name']}"
        )
        
        # Create new connection pool
        pool = SimpleConnectionPool(1, 3, connection_string)
        user_db_pools[user_email] = pool
        
        logger.info(f"✅ Created connection pool for {user_email}")
        return pool
        
    except Exception as e:
        logger.error(f"Failed to create connection pool for {user_email}: {e}")
        return None

def validate_sql_security(sql: str) -> bool:
    """Validate SQL for security (only SELECT and WITH statements allowed)"""
    sql_clean = sql.strip().upper()
    
    # Check for dangerous keywords
    dangerous_keywords = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
        'EXEC', 'EXECUTE', 'CALL', 'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK'
    ]
    
    for keyword in dangerous_keywords:
        if keyword in sql_clean:
            logger.warning(f"Blocked SQL containing dangerous keyword: {keyword}")
            return False
    
    # Only allow SELECT and WITH statements
    if not sql_clean.startswith(('SELECT', 'WITH')):
        logger.warning(f"Blocked SQL not starting with SELECT or WITH: {sql_clean[:50]}...")
        return False
    
    # Check for multiple statements (semicolon separated)
    if ';' in sql and not sql_clean.endswith(';'):
        logger.warning("Blocked SQL with multiple statements")
        return False
    
    return True

def execute_sql(sql: str, user_pool: SimpleConnectionPool, limit: int = None) -> Dict[str, Any]:
    """Execute SQL query on user's database"""
    start_time = datetime.now()
    
    try:
        conn = user_pool.getconn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Set query timeout
        cursor.execute(f"SET statement_timeout = {QUERY_TIMEOUT * 1000}")  # milliseconds
        
        # Add LIMIT if not present and limit is specified
        if limit and 'LIMIT' not in sql.upper():
            sql = f"{sql.rstrip(';')} LIMIT {limit}"
        
        # Execute query
        cursor.execute(sql)
        
        # Get results
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Convert rows to list of dicts
        results = [dict(row) for row in rows]
        
        cursor.close()
        user_pool.putconn(conn)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "success": True,
            "sql": sql,
            "columns": columns,
            "rows": results,
            "row_count": len(results),
            "execution_time": execution_time,
            "limit_applied": limit if limit and 'LIMIT' not in sql.upper() else None
        }
        
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return {
            "success": False,
            "sql": sql,
            "error": str(e),
            "execution_time": (datetime.now() - start_time).total_seconds()
        }

@app.tool()
def execute_query(
    sql: str,
    user_email: str = None,
    limit: int = None
) -> Dict[str, Any]:
    """
    Execute a SQL query on the user's database.
    
    Args:
        sql: The SQL query to execute (SELECT or WITH statements only)
        user_email: User's email for authentication (optional if DEFAULT_USER_EMAIL is set)
        limit: Maximum number of rows to return (default: MAX_RESULT_ROWS)
    
    Returns:
        Query results with metadata
    """
    # Use default email if not provided
    if not user_email:
        if DEFAULT_USER_EMAIL:
            user_email = DEFAULT_USER_EMAIL
            logger.info(f"📧 Using default user: {user_email}")
        else:
            return {
                "success": False,
                "error": "user_email is required when email authentication is enabled and no DEFAULT_USER_EMAIL is set",
                "sql": sql
            }
    
    # Security validation
    if not validate_sql_security(sql):
        return {
            "success": False,
            "error": "SQL query contains dangerous operations or invalid syntax. Only SELECT and WITH statements are allowed.",
            "sql": sql,
            "user_email": user_email
        }
    
    # Set default limit
    if limit is None:
        limit = MAX_RESULT_ROWS
    
    try:
        # Get user information
        user_info = get_user_info(user_email)
        if not user_info:
            return {
                "success": False,
                "error": f"User {user_email} not found or not active. Please complete onboarding first.",
                "sql": sql,
                "user_email": user_email
            }
        
        # Get user's database connection pool
        user_pool = get_user_connection_pool(user_email, user_info)
        if not user_pool:
            return {
                "success": False,
                "error": f"Failed to connect to database for user {user_email}",
                "sql": sql,
                "user_email": user_email
            }
        
        # Execute the query
        result = execute_sql(sql, user_pool, limit)
        result["user_email"] = user_email
        
        # Log the query
        logger.info(f"📝 Query executed for {user_email}: {sql[:100]}...")
        
        return result
        
    except Exception as e:
        logger.error(f"Query execution failed for {user_email}: {e}")
        return {
            "success": False,
            "error": str(e),
            "sql": sql,
            "user_email": user_email
        }

@app.tool()
def get_schema(user_email: str = None) -> Dict[str, Any]:
    """
    Get the database schema/catalog for the user's database.
    
    Args:
        user_email: User's email for authentication (optional if DEFAULT_USER_EMAIL is set)
    
    Returns:
        Database schema information
    """
    # Use default email if not provided
    if not user_email:
        if DEFAULT_USER_EMAIL:
            user_email = DEFAULT_USER_EMAIL
            logger.info(f"📧 Using default user: {user_email}")
        else:
            return {
                "success": False,
                "error": "user_email is required when email authentication is enabled and no DEFAULT_USER_EMAIL is set"
            }
    
    try:
        # Get user information
        user_info = get_user_info(user_email)
        if not user_info:
            return {
                "success": False,
                "error": f"User {user_email} not found or not active. Please complete onboarding first.",
                "user_email": user_email
            }
        
        # Return the stored catalog
        catalog = user_info.get('catalog_markdown', '')
        
        return {
            "success": True,
            "user_email": user_email,
            "schema": catalog,
            "catalog_length": len(catalog),
            "database_info": {
                "host": user_info['host'],
                "port": user_info['port'],
                "db_name": user_info['db_name'],
                "db_type": user_info['db_type']
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get schema for {user_email}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_email": user_email
        }

@app.tool()
def health() -> Dict[str, Any]:
    """
    Check the health status of the MCP server and database connections.
    
    Returns:
        Health status information
    """
    try:
        # Test admin database connection
        admin_status = "healthy"
        admin_error = None
        try:
            conn = get_admin_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return_admin_db_connection(conn)
        except Exception as e:
            admin_status = "unhealthy"
            admin_error = str(e)
        
        # Count active user pools
        active_pools = len(user_db_pools)
        
        return {
            "status": "healthy" if admin_status == "healthy" else "degraded",
            "timestamp": datetime.now().isoformat(),
            "admin_database": admin_status,
            "admin_error": admin_error,
            "active_user_pools": active_pools,
            "features": {
                "email_authentication": REQUIRE_EMAIL_AUTH,
                "multi_tenant": REQUIRE_EMAIL_AUTH,
                "query_execution": True,
                "schema_access": True,
                "security_validation": True
            },
            "configuration": {
                "max_result_rows": MAX_RESULT_ROWS,
                "query_timeout": QUERY_TIMEOUT,
                "user_connections_table": USER_CONNECTIONS_TABLE,
                "audit_log_table": AUDIT_LOG_TABLE,
                "default_user_email": DEFAULT_USER_EMAIL or "not_set"
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Cleanup function
def cleanup_connections():
    """Clean up all database connections"""
    global admin_db_pool, user_db_pools
    
    if admin_db_pool:
        admin_db_pool.closeall()
        logger.info("Closed admin database pool")
    
    for email, pool in user_db_pools.items():
        pool.closeall()
        logger.info(f"Closed connection pool for {email}")
    
    user_db_pools.clear()

# Startup logging
logger.info("=" * 80)
logger.info("🚀 AnalyticsSQL Database Service v2")
logger.info("📊 Admin DB: " + ADMIN_DB_CONNECTION.split('@')[1] if '@' in ADMIN_DB_CONNECTION else ADMIN_DB_CONNECTION)
logger.info(f"🔐 Email Auth: {'Enabled' if REQUIRE_EMAIL_AUTH else 'Disabled'}")
logger.info(f"📧 Default User: {DEFAULT_USER_EMAIL or 'Not set'}")
logger.info(f"📋 User Table: {USER_CONNECTIONS_TABLE}")
logger.info(f"📝 Audit Table: {AUDIT_LOG_TABLE}")
logger.info(f"📊 Max Rows: {MAX_RESULT_ROWS}")
logger.info(f"⏱️  Query Timeout: {QUERY_TIMEOUT}s")
logger.info("🧠 Architecture: User's LLM → MCP Server → Database")
logger.info("=" * 80)

if __name__ == "__main__":
    import atexit
    atexit.register(cleanup_connections)
    app.run()
