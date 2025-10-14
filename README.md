# AnalyticsSQL - Text-to-SQL MCP Server

A powerful Model Context Protocol (MCP) server that converts natural language queries to SQL using OpenAI with automatic error correction and multi-tenant support.

## 🚀 Features

- **Natural Language to SQL**: Convert questions like "Show me top 5 users by order count" into SQL
- **Automatic Error Correction**: When SQL fails, the server automatically fixes it using OpenAI
- **Multi-Tenant Support**: Each user queries their own database with email-based authentication
- **Real-time Feedback**: Live progress updates during query processing
- **Retry Logic**: Up to 5 attempts to get the query right
- **Security**: Only SELECT queries allowed, dangerous keywords blocked
- **FastMCP Integration**: Clean, production-ready server implementation
- **PostgreSQL Support**: Works with your existing PostgreSQL database

## 🏗️ Architecture

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
             │
             ▼
┌─────────────────────────────────────┐
│   MCP Server (FastMCP)              │  Text-to-SQL queries
│   - Email authentication            │
│   - User-specific DB pools          │
│   - Query generation & execution    │
└─────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL database
- OpenAI API key
- macOS, Linux, or Windows with PostgreSQL installed

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
# LLM Configuration
# ============================================================================
OPENAI_API_KEY=sk-your-openai-key-here
LLM_MODEL=gpt-4o-mini

# ============================================================================
# Query Configuration
# ============================================================================
MAX_RETRIES=5
ENABLE_QUERY_CACHE=true
```

### 4. Setup Admin Database

```bash
cd onboarding_DB/backend
python setup_admin_db.py
cd ../..
```

### 5. Start the Onboarding System

```bash
cd onboarding_DB
./start.sh
```

This starts both:
- **Backend API**: `http://localhost:8001`
- **Frontend UI**: `http://localhost:3001`

### 6. Onboard Your Database

1. Navigate to `http://localhost:3001/onboard`
2. Enter your email and database connection details
3. Optionally select specific tables
4. Generate and review your database catalog
5. Save to complete onboarding

### 7. Start the MCP Server

```bash
python mcp_server.py
```

## 🛠️ Available Tools

### `text_to_sql(query, execute=True, limit=100)`
Main tool for natural language to SQL conversion with auto-retry.

**Examples**:
- "Show me users who have placed orders"
- "What's the total revenue by category?"
- "Top 5 products by price"

### `get_schema()`
Get the complete database schema catalog in markdown format.

### `health()`
Check server and database health status.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REQUIRE_EMAIL_AUTH` | Enable multi-tenant email auth | `true` | Yes |
| `ADMIN_DB_CONNECTION` | Admin database connection string | - | Yes (if auth enabled) |
| `DEFAULT_USER_EMAIL` | Default user email (development) | - | No |
| `OPENAI_API_KEY` | OpenAI API key | - | Yes |
| `LLM_MODEL` | OpenAI model to use | `gpt-4o-mini` | No |
| `MAX_RETRIES` | Max retry attempts for SQL fixes | `5` | No |
| `ENABLE_QUERY_CACHE` | Enable query result caching | `true` | No |

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