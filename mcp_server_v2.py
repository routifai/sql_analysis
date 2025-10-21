#!/usr/bin/env python3
"""
AnalyticsSQL MCP Server v2 - Database Execution Service with Table Access Control
Clean architecture: User's LLM handles text-to-SQL, MCP server handles database operations
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
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


class TableAccessValidator:
    """
    Robust SQL parser to extract and validate table access.
    Handles: CTEs, subqueries, schema-qualified names, aliases, JOINs
    """
    
    def __init__(self, allowed_tables: Set[str], allowed_schemas: Set[str] = None):
        """
        Initialize validator with allowed tables and schemas.
        
        Args:
            allowed_tables: Set of allowed table names (lowercase)
            allowed_schemas: Set of allowed schema names (lowercase). If None, any schema is allowed.
        """
        self.allowed_tables = {t.lower() for t in allowed_tables}
        self.allowed_schemas = {s.lower() for s in allowed_schemas} if allowed_schemas else None
        
    def extract_tables_from_sql(self, sql: str) -> Set[Tuple[Optional[str], str]]:
        """
        Extract all table references from SQL.
        
        Returns:
            Set of (schema, table_name) tuples. Schema is None if not qualified.
        """
        # Remove comments
        sql = self._remove_comments(sql)
        
        # Remove string literals to avoid false positives
        sql = self._remove_string_literals(sql)
        
        tables = set()
        
        # Pattern 1: FROM clause
        # Matches: FROM table, FROM schema.table, FROM "quoted_table", FROM schema."quoted_table"
        from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?|"[^"]+"(?:\."[^"]+")?|`[^`]+`(?:\.[`][^`]+`)?)'
        tables.update(self._extract_from_pattern(sql, from_pattern))
        
        # Pattern 2: JOIN clauses (INNER, LEFT, RIGHT, FULL, CROSS)
        join_pattern = r'\b(?:INNER\s+|LEFT\s+(?:OUTER\s+)?|RIGHT\s+(?:OUTER\s+)?|FULL\s+(?:OUTER\s+)?|CROSS\s+)?JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?|"[^"]+"(?:\."[^"]+")?|`[^`]+`(?:\.[`][^`]+`)?)'
        tables.update(self._extract_from_pattern(sql, join_pattern))
        
        # Pattern 3: UPDATE statements (in case we add them later)
        # Currently blocked by security validation, but good to have
        update_pattern = r'\bUPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
        tables.update(self._extract_from_pattern(sql, update_pattern))
        
        # Pattern 4: INSERT INTO (in case we add them later)
        insert_pattern = r'\bINSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]*)?)'
        tables.update(self._extract_from_pattern(sql, insert_pattern))
        
        # Pattern 5: Tables in CTEs (WITH clause)
        tables.update(self._extract_cte_tables(sql))
        
        # Pattern 6: Tables in subqueries
        tables.update(self._extract_subquery_tables(sql))
        
        return tables
    
    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments"""
        # Remove single-line comments
        sql = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
        # Remove multi-line comments
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        return sql
    
    def _remove_string_literals(self, sql: str) -> str:
        """Remove string literals to avoid matching table names in strings"""
        # Remove single-quoted strings
        sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
        # Remove double-quoted identifiers (but these might be table names, so be careful)
        # We'll keep them for now as they might be quoted table names
        return sql
    
    def _extract_from_pattern(self, sql: str, pattern: str) -> Set[Tuple[Optional[str], str]]:
        """Extract table references matching a pattern"""
        tables = set()
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        
        for match in matches:
            table_ref = match.group(1)
            schema, table = self._parse_table_reference(table_ref)
            tables.add((schema, table))
        
        return tables
    
    def _extract_cte_tables(self, sql: str) -> Set[Tuple[Optional[str], str]]:
        """Extract tables from WITH (CTE) clauses"""
        tables = set()
        
        # Match WITH clause and everything until the main SELECT
        with_match = re.search(r'\bWITH\s+(.*?)\s+SELECT\b', sql, re.IGNORECASE | re.DOTALL)
        if not with_match:
            return tables
        
        cte_section = with_match.group(1)
        
        # Split by comma at the top level (not inside parentheses)
        cte_definitions = self._split_ctes(cte_section)
        
        for cte_def in cte_definitions:
            # Extract the CTE body (everything inside AS (...))
            body_match = re.search(r'\bAS\s*\((.*)\)', cte_def, re.IGNORECASE | re.DOTALL)
            if body_match:
                cte_body = body_match.group(1)
                # Recursively extract tables from CTE body
                tables.update(self.extract_tables_from_sql(cte_body))
        
        # IMPORTANT: Also extract tables from the main SELECT after WITH
        main_select_start = with_match.end() - 6  # Back up to include "SELECT"
        main_select = sql[main_select_start:]
        
        # Don't recurse here - just extract FROM/JOIN from main query
        # to avoid infinite recursion
        tables.update(self._extract_from_pattern(main_select, 
            r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?|"[^"]+"(?:\."[^"]+")?|`[^`]+`(?:\.[`][^`]+`)?)'))
        
        return tables
    
    def _split_ctes(self, cte_section: str) -> List[str]:
        """Split multiple CTE definitions by comma, respecting parentheses"""
        result = []
        current = ""
        paren_depth = 0
        
        for char in cte_section:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                result.append(current.strip())
                current = ""
                continue
            
            current += char
        
        if current.strip():
            result.append(current.strip())
        
        return result
    
    def _extract_subquery_tables(self, sql: str) -> Set[Tuple[Optional[str], str]]:
        """Extract tables from subqueries"""
        tables = set()
        
        # Pattern 1: FROM subqueries
        from_positions = [m.start() for m in re.finditer(r'\bFROM\s*\(', sql, re.IGNORECASE)]
        
        # Pattern 2: JOIN subqueries
        join_positions = [m.start() for m in re.finditer(
            r'\b(?:INNER\s+|LEFT\s+(?:OUTER\s+)?|RIGHT\s+(?:OUTER\s+)?|FULL\s+(?:OUTER\s+)?|CROSS\s+)?JOIN\s*\(',
            sql, re.IGNORECASE
        )]
        
        all_positions = from_positions + join_positions
        
        for pos in all_positions:
            # Find the opening parenthesis
            paren_pos = sql.find('(', pos)
            if paren_pos != -1:
                subquery = self._extract_balanced_parens(sql, paren_pos)
                if subquery:
                    tables.update(self.extract_tables_from_sql(subquery))
        
        return tables
    
    def _extract_balanced_parens(self, sql: str, start_pos: int) -> Optional[str]:
        """Extract content between balanced parentheses starting at start_pos"""
        if start_pos >= len(sql) or sql[start_pos] != '(':
            return None
        
        depth = 0
        end_pos = start_pos
        
        for i in range(start_pos, len(sql)):
            if sql[i] == '(':
                depth += 1
            elif sql[i] == ')':
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break
        
        if depth == 0 and end_pos > start_pos:
            return sql[start_pos + 1:end_pos]  # Exclude the outer parentheses
        
        return None
    
    def _parse_table_reference(self, table_ref: str) -> Tuple[Optional[str], str]:
        """
        Parse a table reference into (schema, table_name).
        
        Examples:
            'users' -> (None, 'users')
            'public.users' -> ('public', 'users')
            '"Schema"."Table"' -> ('Schema', 'Table')  # Preserve case
            '`schema`.`table`' -> ('schema', 'table')
        """
        # Check if schema.table format (quoted or unquoted)
        if '.' in table_ref:
            # Handle quoted schema and table: "schema"."table" or `schema`.`table`
            parts = table_ref.split('.')
            
            schema = parts[0].strip()
            table = parts[1].strip()
            
            # Remove quotes from each part individually
            schema = self._unquote_identifier(schema)
            table = self._unquote_identifier(table)
            
            return (schema, table)
        else:
            # Single table name
            table = self._unquote_identifier(table_ref)
            return (None, table)
    
    def _unquote_identifier(self, identifier: str) -> str:
        """Remove quotes from identifier, preserving case if quoted"""
        identifier = identifier.strip()
        
        # Check if quoted
        if (identifier.startswith('"') and identifier.endswith('"')) or \
           (identifier.startswith('`') and identifier.endswith('`')):
            # Quoted - preserve case
            return identifier[1:-1]
        else:
            # Unquoted - lowercase (SQL standard)
            return identifier.lower()
    
    def validate(self, sql: str) -> Tuple[bool, Optional[str], Set[str]]:
        """
        Validate that SQL only accesses allowed tables.
        
        Returns:
            (is_valid, error_message, unauthorized_tables)
        """
        try:
            referenced_tables = self.extract_tables_from_sql(sql)
            
            if not referenced_tables:
                return False, "No tables found in query. Please check your SQL syntax.", set()
            
            unauthorized = set()
            
            for schema, table in referenced_tables:
                # Build full identifier
                full_name = f"{schema}.{table}" if schema else table
                
                # Check table access first
                if table not in self.allowed_tables:
                    unauthorized.add(full_name)
                    continue
                
                # Then check schema access (if restrictions enabled)
                if self.allowed_schemas is not None and schema is not None:
                    if schema not in self.allowed_schemas:
                        unauthorized.add(full_name)
            
            if unauthorized:
                error_msg = (
                    f"Access denied to table(s): {', '.join(sorted(unauthorized))}. "
                    f"You can only query the following tables: {', '.join(sorted(self.allowed_tables))}"
                )
                return False, error_msg, unauthorized
            
            return True, None, set()
            
        except Exception as e:
            logger.error(f"Table validation error: {e}")
            return False, f"Table validation failed: {str(e)}", set()


def extract_catalog_tables(catalog_markdown: str) -> Tuple[Set[str], Set[str]]:
    """
    Extract table names and schemas from catalog markdown.
    
    Expected formats:
        - ## Table: `table_name`
        - ### table_name
        - ### schema.table_name
        - **Table:** `schema.table_name`
    
    Returns:
        (tables, schemas) - both as lowercase sets
    """
    tables = set()
    schemas = set()
    
    if not catalog_markdown:
        return tables, schemas
    
    lines = catalog_markdown.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Pattern 1: Table headers like "## Table: `table_name`"
        if line.startswith('## Table:'):
            # Extract table name from backticks
            match = re.search(r'`([^`]+)`', line)
            if match:
                table_name = match.group(1).strip()
                schema, table = _parse_table_name(table_name)
                if table:
                    tables.add(table.lower())
                if schema:
                    schemas.add(schema.lower())
        
        # Pattern 2: Schema headers like "### Schema: `schema_name`"
        elif line.startswith('## Schema:') or line.startswith('### Schema:'):
            match = re.search(r'`([^`]+)`', line)
            if match:
                schema_name = match.group(1).strip()
                schemas.add(schema_name.lower())
        
        # Pattern 3: Simple table headers like "### table_name"
        elif line.startswith('###') and not line.startswith('####'):
            # Remove markdown symbols and clean
            cleaned = line.lstrip('#').strip()
            # Remove common prefixes like "Table:", "Schema:", etc.
            cleaned = re.sub(r'^(Table|Schema|View):\s*', '', cleaned, flags=re.IGNORECASE)
            # Remove markdown formatting like **, `, etc.
            cleaned = cleaned.strip('*').strip('`').strip('"').strip("'")
            
            # Only process if it looks like a table name
            if cleaned and re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', cleaned):
                # Skip generic section headers (they usually have no backticks and no columns below)
                if len(cleaned) > 30 or cleaned.lower() in ['overview', 'summary', 'description', 'introduction']:
                    continue
                schema, table = _parse_table_name(cleaned)
                if table:
                    tables.add(table.lower())
                if schema:
                    schemas.add(schema.lower())
        
        # Pattern 4: Inline table references with backticks
        # Example: **Table:** `users` or Table: `schema.users`
        elif '`' in line and ('Table:' in line or 'table' in line.lower()):
            inline_matches = re.findall(r'`([a-zA-Z_][a-zA-Z0-9_.]*)`', line)
            for match in inline_matches:
                if re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', match):  # Valid identifier
                    schema, table = _parse_table_name(match)
                    if table:
                        tables.add(table.lower())
                    if schema:
                        schemas.add(schema.lower())
    
    return tables, schemas


def _parse_table_name(name: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse schema.table or just table"""
    if '.' in name:
        parts = name.split('.')
        return parts[0].strip(), parts[1].strip()
    else:
        return None, name.strip()


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


def validate_sql_security(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SQL for security (only SELECT and WITH statements allowed).
    
    Returns:
        (is_valid, error_message)
    """
    sql_clean = sql.strip().upper()
    
    if not sql_clean:
        return False, "Empty SQL query"
    
    # Check for dangerous keywords
    dangerous_keywords = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
        'EXEC', 'EXECUTE', 'CALL', 'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK'
    ]
    
    for keyword in dangerous_keywords:
        # Use word boundaries to avoid false positives (e.g., "DESCRIPTION" contains "SCRIPT")
        if re.search(r'\b' + keyword + r'\b', sql_clean):
            return False, f"SQL contains forbidden keyword: {keyword}. Only SELECT and WITH statements are allowed."
    
    # Only allow SELECT and WITH statements
    if not sql_clean.startswith(('SELECT', 'WITH')):
        return False, f"SQL must start with SELECT or WITH. Found: {sql_clean[:50]}..."
    
    # Check for multiple statements (semicolon separated)
    # Allow trailing semicolon but not multiple statements
    semicolon_count = sql.count(';')
    if semicolon_count > 1:
        return False, "Multiple SQL statements not allowed. Please execute one query at a time."
    
    if semicolon_count == 1 and not sql.strip().endswith(';'):
        return False, "Multiple SQL statements not allowed. Please execute one query at a time."
    
    return True, None


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
    
    Security features:
    - Only SELECT and WITH statements allowed
    - Only tables in user's catalog can be accessed
    - Query timeout enforcement
    - Row limit enforcement
    
    Args:
        sql: The SQL query to execute (SELECT or WITH statements only)
        user_email: User's email for authentication (optional if DEFAULT_USER_EMAIL is set)
        limit: Maximum number of rows to return (default: MAX_RESULT_ROWS)
    
    Returns:
        Query results with metadata including success status, rows, columns, and execution time
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
    
    # Security validation - check for dangerous operations
    is_valid, error_msg = validate_sql_security(sql)
    if not is_valid:
        logger.warning(f"🚫 Security validation failed for {user_email}: {error_msg}")
        return {
            "success": False,
            "error": error_msg,
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
        
        # Extract allowed tables from catalog
        catalog = user_info.get('catalog_markdown', '')
        allowed_tables, allowed_schemas = extract_catalog_tables(catalog)
        
        if not allowed_tables:
            logger.warning(f"⚠️ No tables found in catalog for {user_email}")
            return {
                "success": False,
                "error": "No tables found in your catalog. Your schema may not be initialized. Please contact your administrator.",
                "sql": sql,
                "user_email": user_email
            }
        
        # Validate table access
        validator = TableAccessValidator(
            allowed_tables=allowed_tables,
            allowed_schemas=allowed_schemas if allowed_schemas else None
        )
        
        is_valid, error_msg, unauthorized_tables = validator.validate(sql)
        
        if not is_valid:
            logger.warning(f"🚫 Table access violation for {user_email}: {error_msg}")
            logger.warning(f"   Unauthorized tables: {unauthorized_tables}")
            logger.warning(f"   Allowed tables: {allowed_tables}")
            return {
                "success": False,
                "error": error_msg,
                "sql": sql,
                "user_email": user_email,
                "allowed_tables": sorted(list(allowed_tables)),
                "unauthorized_tables": sorted(list(unauthorized_tables))
            }
        
        logger.info(f"✅ Table access validated for {user_email}")
        
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
        result["tables_accessed"] = sorted(list(allowed_tables & {t for _, t in validator.extract_tables_from_sql(sql)}))
        
        # Log the query
        if result["success"]:
            logger.info(f"📝 Query executed successfully for {user_email}: {sql[:100]}...")
        else:
            logger.error(f"❌ Query failed for {user_email}: {result.get('error', 'Unknown error')}")
        
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
    
    This returns the pre-computed catalog that defines which tables the user can access.
    Only tables listed in this catalog can be queried.
    
    Args:
        user_email: User's email for authentication (optional if DEFAULT_USER_EMAIL is set)
    
    Returns:
        Database schema information including catalog markdown and allowed tables list
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
        
        # Extract table list for convenience
        allowed_tables, allowed_schemas = extract_catalog_tables(catalog)
        
        return {
            "success": True,
            "user_email": user_email,
            "schema": catalog,
            "catalog_length": len(catalog),
            "allowed_tables": sorted(list(allowed_tables)),
            "allowed_schemas": sorted(list(allowed_schemas)) if allowed_schemas else None,
            "table_count": len(allowed_tables),
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
        Health status information including admin DB status, active pools, and configuration
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
                "security_validation": True,
                "table_access_control": True
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
logger.info("🚀 AnalyticsSQL Database Service v2 - SECURED")
logger.info("🔒 Table Access Control: ENABLED")
logger.info("📊 Admin DB: " + ADMIN_DB_CONNECTION.split('@')[1] if '@' in ADMIN_DB_CONNECTION else ADMIN_DB_CONNECTION)
logger.info(f"🔐 Email Auth: {'Enabled' if REQUIRE_EMAIL_AUTH else 'Disabled'}")
logger.info(f"📧 Default User: {DEFAULT_USER_EMAIL or 'Not set'}")
logger.info(f"📋 User Table: {USER_CONNECTIONS_TABLE}")
logger.info(f"📝 Audit Table: {AUDIT_LOG_TABLE}")
logger.info(f"📊 Max Rows: {MAX_RESULT_ROWS}")
logger.info(f"⏱️  Query Timeout: {QUERY_TIMEOUT}s")
logger.info("🧠 Architecture: User's LLM → MCP Server → Database")
logger.info("🛡️  Security: Only cataloged tables can be accessed")
logger.info("=" * 80)

if __name__ == "__main__":
    import atexit
    atexit.register(cleanup_connections)
    app.run()