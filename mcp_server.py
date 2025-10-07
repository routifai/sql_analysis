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
from typing import Dict, Any, List
from decimal import Decimal
import hashlib

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
ENABLE_QUERY_CACHE = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"

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
# Query Cache (Simple in-memory for POC)
# ============================================================================

query_cache = {}  # {query_hash: {sql, success, results, timestamp}}

def cache_query(query: str, sql: str, success: bool, results: Dict = None):
    """Cache successful queries for reuse"""
    if not ENABLE_QUERY_CACHE:
        return
    
    query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
    query_cache[query_hash] = {
        'query': query,
        'sql': sql,
        'success': success,
        'results': results if success else None,
        'timestamp': datetime.now().isoformat()
    }
    logger.info(f"📦 Cached query: {query[:50]}...")

def get_cached_query(query: str) -> Dict | None:
    """Check if query was already solved"""
    if not ENABLE_QUERY_CACHE:
        return None
    
    query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
    cached = query_cache.get(query_hash)
    
    if cached and cached['success']:
        logger.info(f"🎯 Cache hit for: {query[:50]}...")
        return cached
    
    return None

# ============================================================================
# Relationship Map (Define your schema relationships)
# ============================================================================

# TODO: Update this based on YOUR actual database schema
RELATIONSHIP_MAP = """
TABLE RELATIONSHIPS:
- users.user_id → usage_records.user_id (1:N - one user has many usage records)
- users.lob → lob_summary.lob_name (N:1 - many users per LOB)

IMPORTANT JOIN PATTERNS:
- To get user activity: JOIN users u WITH usage_records ur ON u.user_id = ur.user_id
- To get LOB details: JOIN users u WITH lob_summary ls ON u.lob = ls.lob_name
- For user activity by LOB: users → usage_records → group by users.lob
"""

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
# Two-Stage SQL Generation with Chain-of-Thought
# ============================================================================

async def generate_query_plan(user_query: str, catalog: str, ctx: Context = None) -> str:
    """
    Stage 1: Generate reasoning plan (Chain-of-Thought)
    """
    
    if ctx:
        await ctx.info("🧠 Stage 1: Generating query plan...")
    
    prompt = f"""You are a SQL query planner. Break down how to answer this question using the database.

DATABASE SCHEMA:
{catalog}

{RELATIONSHIP_MAP}

USER QUESTION: {user_query}

INSTRUCTIONS:
Think step-by-step and create a query plan. Include:
1. Which tables are needed
2. What columns to select
3. How to join tables (use relationship map)
4. What filters to apply
5. Any aggregations needed
6. Sort order if relevant

Return your plan as a numbered list. Be specific about table names and columns.

QUERY PLAN:"""
    
    response = llm_client.client.chat.completions.create(
        model=llm_client.model,
        max_tokens=1500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    plan = response.choices[0].message.content.strip()
    logger.info(f"📋 Query Plan:\n{plan}")
    
    return plan


async def generate_sql_from_plan(
    user_query: str,
    plan: str,
    catalog: str,
    ctx: Context = None
) -> str:
    """
    Stage 2: Generate SQL based on the reasoning plan
    """
    
    if ctx:
        await ctx.info("⚙️ Stage 2: Generating SQL from plan...")
    
    prompt = f"""You are a PostgreSQL expert. Generate SQL based on this query plan.

DATABASE SCHEMA:
{catalog}

{RELATIONSHIP_MAP}

USER QUESTION: {user_query}

QUERY PLAN:
{plan}

INSTRUCTIONS:
- Follow the plan exactly
- Use proper JOIN syntax based on relationships
- Use table aliases (e.g., users u, usage_records ur)
- Column names are case-sensitive
- Return ONLY the SQL query, no explanations

SQL:"""
    
    response = llm_client.client.chat.completions.create(
        model=llm_client.model,
        max_tokens=2000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    sql = response.choices[0].message.content.strip()
    sql = sql.replace('```sql', '').replace('```', '').strip()
    
    logger.info(f"🔧 Generated SQL: {sql[:150]}...")
    
    return sql


async def fix_sql_with_context(
    user_query: str,
    plan: str,
    failed_sql: str,
    error: str,
    catalog: str,
    ctx: Context = None
) -> str:
    """
    Fix SQL with context from original plan
    """
    
    if ctx:
        await ctx.info("🔧 Fixing SQL with plan context...")
    
    prompt = f"""Fix this SQL query that failed.

DATABASE SCHEMA:
{catalog}

{RELATIONSHIP_MAP}

ORIGINAL QUESTION: {user_query}

QUERY PLAN (your reasoning):
{plan}

FAILED SQL:
{failed_sql}

ERROR:
{error}

INSTRUCTIONS:
- The plan is correct, but SQL has an error
- Fix the SQL based on the error message
- Keep following the original plan
- Common issues: wrong column names, missing JOINs, type mismatches
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
    
    logger.info(f"🔧 Fixed SQL: {fixed_sql[:150]}...")
    
    return fixed_sql


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
async def text_to_sql(
    query: str,
    execute: bool = True,
    limit: int = 100,
    use_cache: bool = True,
    ctx: Context = None
) -> str:
    """
    Convert natural language to SQL with two-stage reasoning and auto-retry.
    
    This version uses Chain-of-Thought reasoning:
    1. First generates a query plan (which tables, joins, filters)
    2. Then generates SQL based on that plan
    3. If errors occur, fixes SQL while maintaining the plan
    
    Args:
        query: Your question in natural language
        execute: Whether to execute the SQL (default: True)
        limit: Maximum rows to return (default: 100)
        use_cache: Check cache for similar queries (default: True)
    
    Returns:
        JSON with plan, SQL, results, and metadata
    """
    
    if ctx:
        await ctx.info(f"📝 Query: {query[:100]}...")
    
    start_time = datetime.now()
    
    try:
        # Check cache first
        if use_cache and execute:
            cached = get_cached_query(query)
            if cached:
                if ctx:
                    await ctx.info("🎯 Using cached result!")
                
                return json.dumps({
                    'query': query,
                    'sql': cached['sql'],
                    'success': True,
                    'cached': True,
                    'columns': cached['results']['columns'] if cached['results'] else [],
                    'rows': (cached['results']['rows'][:limit] if cached['results'] else []),
                    'row_count': len(cached['results']['rows'][:limit]) if cached['results'] else 0,
                    'total_time': 0.001  # Instant from cache
                }, indent=2, default=str)
        
        # Stage 1: Generate query plan
        plan = await generate_query_plan(query, catalog_content, ctx)
        
        # Stage 2: Generate SQL from plan
        sql = await generate_sql_from_plan(query, plan, catalog_content, ctx)
        
        if not execute:
            return json.dumps({
                'query': query,
                'plan': plan,
                'sql': sql,
                'executed': False,
                'total_time': (datetime.now() - start_time).total_seconds()
            }, indent=2)
        
        # Execute with retry (now with plan context)
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
                        'plan': plan,
                        'sql': current_sql,
                        'success': False,
                        'error': f"Validation error: {error_msg}",
                        'attempts': attempt + 1
                    }, indent=2)
                
                # Fix with plan context
                current_sql = await fix_sql_with_context(
                    query, plan, current_sql, error_msg, catalog_content, ctx
                )
                continue
            
            # Execute
            result = execute_sql(current_sql)
            
            if result['success']:
                if ctx:
                    await ctx.info(
                        f"✅ Success! {result['row_count']} rows in {result['execution_time']:.2f}s"
                    )
                
                # Cache successful query
                cache_query(query, result['sql'], True, result)
                
                response = {
                    'query': query,
                    'plan': plan,
                    'sql': result['sql'],
                    'success': True,
                    'cached': False,
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
                    'plan': plan,
                    'sql': result['sql'],
                    'success': False,
                    'error': result['error'],
                    'attempts': attempt + 1
                }, indent=2)
            
            # Fix with plan context
            if ctx:
                await ctx.info("🔧 Attempting to fix SQL with plan context...")
            
            current_sql = await fix_sql_with_context(
                query, plan, current_sql, result['error'], catalog_content, ctx
            )
        
        return json.dumps({
            'query': query,
            'plan': plan,
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
async def get_cache_stats() -> str:
    """Get query cache statistics"""
    total = len(query_cache)
    successful = sum(1 for q in query_cache.values() if q['success'])
    
    return json.dumps({
        'cache_enabled': ENABLE_QUERY_CACHE,
        'total_cached_queries': total,
        'successful_queries': successful,
        'cache_size_mb': len(str(query_cache)) / 1024 / 1024
    }, indent=2)


@mcp.tool()
async def clear_cache() -> str:
    """Clear the query cache"""
    query_cache.clear()
    return json.dumps({'message': 'Cache cleared', 'success': True}, indent=2)


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
        'max_retries': MAX_RETRIES,
        'cache_enabled': ENABLE_QUERY_CACHE,
        'cached_queries': len(query_cache),
        'features': {
            'two_stage_reasoning': True,
            'relationship_hints': True,
            'query_caching': ENABLE_QUERY_CACHE
        }
    }, indent=2)


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🚀 Text-to-SQL MCP Server v2.0 (Two-Stage Reasoning)")
    logger.info(f"🤖 Model: {llm_client.model}")
    logger.info(f"📄 Catalog: {CATALOG_PATH} ({len(catalog_content)} chars)")
    logger.info(f"🔄 Max Retries: {MAX_RETRIES}")
    logger.info(f"💾 Query Cache: {'Enabled' if ENABLE_QUERY_CACHE else 'Disabled'}")
    logger.info(f"🧠 Features: Two-Stage Reasoning + Relationship Hints")
    logger.info("=" * 80)
    
    try:
        # Run with Streamable HTTP
        mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
    finally:
        db_pool.closeall()
