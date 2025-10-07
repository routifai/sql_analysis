#!/usr/bin/env python3
"""
Text-to-SQL MCP Server with Auto-Retry
FastMCP 2.12.1 + Streamable HTTP
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Import shared LLM client
from llm_client import get_llm_client

# Load environment
load_dotenv()

# Configuration
DB_CONNECTION = os.getenv("DB_CONNECTION_STRING")
CATALOG_PATH = os.getenv("CATALOG_PATH", "database_catalog.md")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate config
if not DB_CONNECTION:
    logger.error("❌ Missing DB_CONNECTION_STRING")
    exit(1)

# Initialize
mcp = FastMCP("text2sql")
llm_client = get_llm_client()
db_pool = SimpleConnectionPool(2, 10, DB_CONNECTION)

# Load catalog
catalog_content = ""
if Path(CATALOG_PATH).exists():
    with open(CATALOG_PATH, 'r') as f:
        catalog_content = f.read()
    logger.info(f"✅ Loaded catalog: {len(catalog_content)} chars")
else:
    logger.warning(f"⚠️ Catalog not found: {CATALOG_PATH}")

# ============================================================================
# Utilities
# ============================================================================

def serialize_value(value):
    """Convert DB values to JSON-serializable"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()[:50]
    return str(value)


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate SQL is safe"""
    sql_upper = sql.strip().upper()
    
    if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
        return False, "Only SELECT queries allowed"
    
    dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'TRUNCATE', 'ALTER', 'CREATE']
    for keyword in dangerous:
        if f' {keyword} ' in f' {sql_upper} ':
            return False, f"Keyword '{keyword}' not allowed"
    
    if sql.count(';') > 1:
        return False, "Multiple statements not allowed"
    
    return True, ""


def execute_sql(sql: str) -> Dict[str, Any]:
    """Execute SQL query"""
    sql_clean = sql.strip().rstrip(';')
    if 'LIMIT' not in sql_clean.upper():
        sql_clean += " LIMIT 1000"
    
    conn = None
    cursor = None
    start = datetime.now()
    
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SET statement_timeout = 30000")
        cursor.execute(sql_clean)
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        serialized = [
            {k: serialize_value(v) for k, v in dict(row).items()}
            for row in rows
        ]
        
        return {
            'success': True,
            'sql': sql_clean,
            'columns': columns,
            'rows': serialized,
            'row_count': len(serialized),
            'execution_time': (datetime.now() - start).total_seconds()
        }
        
    except Exception as e:
        return {
            'success': False,
            'sql': sql_clean,
            'error': str(e),
            'execution_time': (datetime.now() - start).total_seconds()
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)


# ============================================================================
# LLM Functions
# ============================================================================

async def generate_sql(user_query: str, catalog: str) -> str:
    """Generate SQL using shared LLM client"""
    
    prompt = f"""You are a PostgreSQL expert. Generate a SQL query for this question.

DATABASE SCHEMA:
{catalog}

RULES:
- Return ONLY the SQL query, no explanations
- Use proper JOINs when needed
- Use table aliases (e.g., users u)
- Column names are case-sensitive
- Do NOT add LIMIT unless user asks for it

USER QUESTION: {user_query}

SQL:"""
    
    response = llm_client.client.chat.completions.create(
        model=llm_client.model,
        max_tokens=2000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    sql = response.choices[0].message.content.strip()
    sql = sql.replace('```sql', '').replace('```', '').strip()
    
    logger.info(f"Generated SQL: {sql[:100]}...")
    return sql


async def fix_sql(user_query: str, failed_sql: str, error: str, catalog: str) -> str:
    """Fix SQL based on error"""
    
    prompt = f"""Fix this SQL query that failed with an error.

DATABASE SCHEMA:
{catalog}

ORIGINAL QUESTION: {user_query}

FAILED SQL:
{failed_sql}

ERROR:
{error}

INSTRUCTIONS:
- Analyze the error carefully
- Fix the SQL to resolve the error
- Return ONLY the corrected SQL

FIXED SQL:"""
    
    response = llm_client.client.chat.completions.create(
        model=llm_client.model,
        max_tokens=2000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    fixed_sql = response.choices[0].message.content.strip()
    fixed_sql = fixed_sql.replace('```sql', '').replace('```', '').strip()
    
    logger.info(f"Fixed SQL: {fixed_sql[:100]}...")
    return fixed_sql


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
async def text_to_sql(
    query: str,
    execute: bool = True,
    limit: int = 100,
    ctx: Context = None
) -> str:
    """
    Convert natural language to SQL and execute it with auto-retry.
    
    Args:
        query: Your question in natural language (e.g., "Show top 10 users by usage time")
        execute: Whether to execute the SQL (default: True)
        limit: Maximum rows to return (default: 100)
    
    Returns:
        JSON with SQL, results, and metadata
    
    Examples:
        - "How many users are in Finance?"
        - "Top 5 features by usage count"
        - "Average session duration by department"
    """
    
    if ctx:
        await ctx.info(f"📝 Query: {query[:100]}...")
    
    start_time = datetime.now()
    
    try:
        # Generate SQL
        if ctx:
            await ctx.info("🤖 Generating SQL with Claude...")
        
        sql = await generate_sql(query, catalog_content)
        
        if not execute:
            return json.dumps({
                'query': query,
                'sql': sql,
                'executed': False,
                'total_time': (datetime.now() - start_time).total_seconds()
            }, indent=2)
        
        # Execute with retry
        current_sql = sql
        
        for attempt in range(MAX_RETRIES):
            if ctx:
                await ctx.info(f"🔍 Attempt {attempt + 1}/{MAX_RETRIES}")
            
            # Validate
            is_valid, error_msg = validate_sql(current_sql)
            if not is_valid:
                if ctx:
                    await ctx.error(f"❌ Validation failed: {error_msg}")
                
                if attempt == MAX_RETRIES - 1:
                    return json.dumps({
                        'query': query,
                        'sql': current_sql,
                        'success': False,
                        'error': f"Validation error: {error_msg}",
                        'attempts': attempt + 1
                    }, indent=2)
                
                # Try to fix
                current_sql = await fix_sql(query, current_sql, error_msg, catalog_content)
                continue
            
            # Execute
            result = execute_sql(current_sql)
            
            if result['success']:
                if ctx:
                    await ctx.info(f"✅ Success! {result['row_count']} rows in {result['execution_time']:.2f}s")
                
                response = {
                    'query': query,
                    'sql': result['sql'],
                    'success': True,
                    'columns': result['columns'],
                    'rows': result['rows'][:limit],
                    'row_count': min(result['row_count'], limit),
                    'total_rows': result['row_count'],
                    'execution_time': result['execution_time'],
                    'total_time': (datetime.now() - start_time).total_seconds(),
                    'attempts': attempt + 1
                }
                
                return json.dumps(response, indent=2, default=str)
            
            # Failed - log and retry
            if ctx:
                await ctx.warning(f"⚠️ Error: {result['error'][:100]}")
            
            if attempt == MAX_RETRIES - 1:
                return json.dumps({
                    'query': query,
                    'sql': result['sql'],
                    'success': False,
                    'error': result['error'],
                    'attempts': attempt + 1
                }, indent=2)
            
            # Fix and retry
            if ctx:
                await ctx.info("🔧 Attempting to fix SQL...")
            
            current_sql = await fix_sql(query, current_sql, result['error'], catalog_content)
        
        return json.dumps({
            'query': query,
            'success': False,
            'error': 'Max retries exceeded',
            'attempts': MAX_RETRIES
        }, indent=2)
        
    except Exception as e:
        if ctx:
            await ctx.error(f"❌ Error: {e}")
        
        logger.error(f"Error in text_to_sql: {e}", exc_info=True)
        
        return json.dumps({
            'query': query,
            'success': False,
            'error': str(e)
        }, indent=2)


@mcp.tool()
async def get_schema() -> str:
    """Get the complete database schema catalog"""
    return catalog_content


@mcp.tool()
async def health() -> str:
    """Check server health"""
    
    db_ok = False
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        db_pool.putconn(conn)
        db_ok = True
    except:
        pass
    
    return json.dumps({
        'status': 'healthy' if db_ok else 'degraded',
        'database': 'healthy' if db_ok else 'unhealthy',
        'catalog_loaded': len(catalog_content) > 100,
        'model': llm_client.model,
        'max_retries': MAX_RETRIES
    }, indent=2)


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🚀 Text-to-SQL MCP Server")
    logger.info(f"🤖 Model: {llm_client.model}")
    logger.info(f"📄 Catalog: {CATALOG_PATH} ({len(catalog_content)} chars)")
    logger.info(f"🔄 Max Retries: {MAX_RETRIES}")
    logger.info("=" * 80)
    
    try:
        # Run with Streamable HTTP
        mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
    finally:
        db_pool.closeall()
