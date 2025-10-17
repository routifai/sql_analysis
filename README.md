# AnalyticsSQL - Database Execution MCP Server

A clean Model Context Protocol (MCP) server that provides secure database execution services with multi-tenant support. Your LLM handles text-to-SQL conversion, while this server handles database operations.

## 🚀 Features

- **Clean Architecture**: Your LLM handles text-to-SQL, MCP server handles database execution
- **Multi-Tenant Support**: Each user queries their own database with email-based authentication
- **Security First**: Only SELECT and WITH queries allowed, dangerous keywords blocked
- **Schema Access**: Get database schema/catalog for your LLM to use
- **Connection Pooling**: Efficient database connection management per user
- **FastMCP Integration**: Clean, production-ready server implementation
- **PostgreSQL Support**: Works with your existing PostgreSQL database
- **No LLM Dependencies**: Server focuses purely on database operations

## 🏗️ Architecture

**Clean Separation of Concerns:**

```
┌─────────────────────────────────────┐
│   Your LLM (Claude, GPT, etc.)     │  Handles text-to-SQL conversion
│   - Natural language processing     │
│   - SQL generation                  │
│   - Error handling & retry logic    │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   MCP Server (FastMCP)              │  Database execution service
│   - execute_query(sql, user_email)  │
│   - get_schema(user_email)          │
│   - User authentication             │
│   - Connection pooling              │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   User's Database (PostgreSQL)      │  User's actual data
│   - Secure query execution          │
│   - Schema validation               │
└─────────────────────────────────────┘
```

**Onboarding System:**
```
┌─────────────────────────────────────┐
│   Frontend (Next.js - Port 3001)   │  Users onboard their databases
│   - Onboarding Form                 │
│   - Catalog Editor                  │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Backend (FastAPI - Port 8001)    │  Catalog generation & management
│   - Catalog Generation              │
│   - User Management                 │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Admin DB (PostgreSQL)             │  Stores connection info
│   - DB: onboarding_admin            │
│   - User connection credentials     │
│   - Database catalogs               │
└─────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL database
- macOS, Linux, or Windows with PostgreSQL installed
- Your preferred LLM (Claude, GPT, etc.) for text-to-SQL conversion

## 🛠️ Quick Start

### 1. Setup PostgreSQL

For macOS (Homebrew):
```bash
./setup_postgres_macos.sh
```

This creates the test database and admin database needed for the system.

### 2. Install Python Dependencies

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
# ============================================================================
# Multi-Tenant Configuration (Recommended)
# ============================================================================
REQUIRE_EMAIL_AUTH=true
ADMIN_DB_CONNECTION=postgresql://testuser:testpass@localhost:5432/onboarding_admin

# Default user email (optional but recommended for development)
DEFAULT_USER_EMAIL=your.email@example.com

# ============================================================================
# Database Configuration
# ============================================================================
USER_CONNECTIONS_TABLE=db_connection_infos
AUDIT_LOG_TABLE=onboarding_audit_log
MAX_RESULT_ROWS=1000
QUERY_TIMEOUT=30
```

### 4. Configure Onboarding System

Create a single `.env` file for both frontend and backend:

```bash
cd onboarding_DB
cp env.example .env
```

Edit `.env` and configure your settings:

```env
# Backend Configuration
ADMIN_DB_CONNECTION=postgresql://testuser:testpass@localhost:5432/onboarding_admin
USER_CONNECTIONS_TABLE=db_connection_infos
AUDIT_LOG_TABLE=onboarding_audit_log
API_PORT=8001
LOG_LEVEL=INFO

# Frontend Configuration
NEXT_PUBLIC_API_URL=http://localhost:8001
PORT=3001
```

**Note:** This single `.env` file is used by both the frontend and backend.

### 5. Setup Admin Database

```bash
cd backend
python setup_admin_db.py
cd ../..
```

### 6. Start the Onboarding System

```bash
cd onboarding_DB
./start.sh
```

This starts both:
- **Backend API**: `http://localhost:8001`
- **Frontend UI**: `http://localhost:3001`

### 7. Onboard Your Database

1. Navigate to `http://localhost:3001/onboard`
2. Enter your email and database connection details
3. Optionally select specific tables
4. Generate and review your database catalog
5. Save to complete onboarding

### 8. Start the MCP Server

**New Clean Architecture (Recommended):**
```bash
python mcp_server_v2.py
```

**Legacy Architecture (for comparison):**
```bash
python mcp_server.py
```

## 🛠️ Available Tools (v2 - Clean Architecture)

### `execute_query(sql, user_email=None, limit=None)`
Execute a SQL query on the user's database.

**Parameters:**
- `sql`: The SQL query to execute (SELECT or WITH statements only)
- `user_email`: User's email for authentication (optional if DEFAULT_USER_EMAIL is set)
- `limit`: Maximum number of rows to return

**Example:**
```python
# Your LLM generates SQL, then execute it
result = execute_query(
    sql="SELECT * FROM users WHERE created_at > '2024-01-01' LIMIT 10",
    user_email="user@example.com"
)
```

### `get_schema(user_email=None)`
Get the database schema/catalog for your LLM to use.

**Example:**
```python
# Get schema for your LLM to understand the database
schema = get_schema(user_email="user@example.com")
# schema["schema"] contains the markdown catalog
```

### `health()`
Check server and database health status.

## 🛠️ Legacy Tools (v1 - Anti-pattern)

### `text_to_sql(query, user_email=None, execute=True, limit=100)`
⚠️ **Deprecated**: This creates an anti-pattern where the MCP server calls an LLM.

**Why it's bad:**
- Double LLM calls (your LLM → MCP server's LLM)
- Unnecessary complexity and overhead
- Takes control away from your LLM
- Higher latency and costs

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REQUIRE_EMAIL_AUTH` | Enable multi-tenant email auth | `true` | Yes |
| `ADMIN_DB_CONNECTION` | Admin database connection string | - | Yes (if auth enabled) |
| `DEFAULT_USER_EMAIL` | Default user email (development) | - | No |
| `USER_CONNECTIONS_TABLE` | Table name for user connections | `db_connection_infos` | No |
| `AUDIT_LOG_TABLE` | Table name for audit logging | `onboarding_audit_log` | No |
| `MAX_RESULT_ROWS` | Maximum rows to return per query | `1000` | No |
| `QUERY_TIMEOUT` | Query timeout in seconds | `30` | No |

### Email Authentication

The system supports two modes:

#### Multi-Tenant Mode (Recommended)
Each user has their own database and catalog. Users authenticate with their email.

```env
REQUIRE_EMAIL_AUTH=true
ADMIN_DB_CONNECTION=postgresql://user:pass@localhost:5432/onboarding_admin
DEFAULT_USER_EMAIL=your.email@example.com  # Optional for development
```

**Benefits:**
- Complete data isolation per user
- Custom catalogs for each user's schema
- Audit trail tracking
- Scalable to multiple users

#### Legacy Mode (Single Database)
All queries use the same database. No authentication required.

```env
REQUIRE_EMAIL_AUTH=false
DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/mydb
CATALOG_PATH=database_catalog.md
```

**Note:** Legacy mode is deprecated. Use multi-tenant mode for production.

## 🔄 How It Works

1. **Generate SQL**: OpenAI creates SQL from natural language
2. **Validate**: Check for security issues and syntax
3. **Execute**: Run the SQL against PostgreSQL
4. **If Error**: Pass the error message back to OpenAI
5. **Fix**: OpenAI generates corrected SQL
6. **Retry**: Repeat up to 5 times
7. **Success**: Return results with metadata

## 🔒 Security Features

- **Read-only queries**: Only SELECT and WITH statements allowed
- **Dangerous keyword blocking**: DROP, DELETE, UPDATE, INSERT, etc. are blocked
- **Single statement limit**: No multiple statements per query
- **Query timeout**: 30-second timeout for long-running queries
- **Row limits**: Automatic LIMIT addition to prevent large result sets

## 🔗 Integration

### With MCP Clients

The server implements the Model Context Protocol and can be used with any MCP-compatible client.

### With Cursor/Claude Desktop

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "text-to-sql": {
      "command": "python",
      "args": ["/path/to/analyticsSQL/mcp_server.py"]
    }
  }
}
```

## 📊 Example Response

```json
{
  "query": "Show me users who have placed orders",
  "sql": "SELECT DISTINCT u.* FROM users u JOIN orders o ON u.user_id = o.user_id LIMIT 100",
  "success": true,
  "columns": ["user_id", "username", "email", "first_name", "last_name"],
  "rows": [...],
  "row_count": 15,
  "total_rows": 15,
  "execution_time": 0.023,
  "total_time": 1.456,
  "attempts": 1
}
```

## 🐛 Troubleshooting

### Common Issues

#### MCP Server Issues

1. **"User not found or not active"**
   - User needs to complete onboarding first via `http://localhost:3001/onboard`
   - Verify user exists in admin database

2. **"Admin database unhealthy"**
   - Check `ADMIN_DB_CONNECTION` in `.env`
   - Ensure `onboarding_admin` database exists
   - Run `cd onboarding_DB/backend && python setup_admin_db.py`

3. **"Failed to connect to your database"**
   - User's database credentials may be incorrect
   - Database may be down or unreachable
   - Check firewall/network settings

4. **"OpenAI API error"**
   - Verify your `OPENAI_API_KEY` in `.env`
   - Check API quota and billing

#### Onboarding System Issues

1. **Backend won't start**
   - Ensure PostgreSQL is running: `pg_isready`
   - Verify admin database exists: `python setup_admin_db.py`
   - Check Python dependencies: `pip install -r requirements.txt`

2. **Frontend can't connect to backend**
   - Verify backend is running on port 8001
   - Check browser console for CORS errors
   - Ensure no firewall blocking ports

3. **Catalog generation fails**
   - Verify user's database is accessible
   - Check database credentials are correct
   - Ensure network connectivity to database

#### PostgreSQL Setup Issues

1. **PostgreSQL not running**
   - macOS: `brew services start postgresql`
   - Check status: `pg_isready`

2. **Permission denied**
   - Ensure test user has correct permissions
   - Re-run: `./setup_postgres_macos.sh`

## 📈 Performance

- **Typical response time**: 1-3 seconds for simple queries
- **Complex queries**: 3-10 seconds (includes retry logic)
- **Concurrent requests**: Supports multiple simultaneous queries
- **Memory usage**: Low memory footprint with connection pooling

## 📄 License

MIT License

---

**Built with ❤️ using FastMCP, OpenAI GPT-4o Mini, and PostgreSQL**