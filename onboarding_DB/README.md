# Text2SQL Onboarding System

Multi-tenant onboarding system for Text2SQL. Users connect their PostgreSQL databases, generate catalogs, and the system routes queries to their specific databases.

## Architecture

```
┌─────────────────────────────────────┐
│   Frontend (Next.js - Port 3001)   │
│   - Onboarding Form                 │
│   - Catalog Editor                  │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Backend (FastAPI - Port 8001)    │
│   - Catalog Generation              │
│   - User Management                 │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│   Admin DB (PostgreSQL)             │
│   - DB: onboarding_admin            │
│   - Table: db_connection_infos      │
└─────────────────────────────────────┘
```

## Quick Start

### 1. Configure Environment

Copy the example environment file and configure it:

```bash
cd onboarding_DB
cp env.example .env
```

Edit `.env` with your configuration:

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

**Note:** This single `.env` file is used by both frontend and backend.

### 2. Setup Admin Database

```bash
cd backend
python setup_admin_db.py
cd ..
```

This creates the `onboarding_admin` database with the required schema.

### 3. Start the System

Use the convenient startup script:

```bash
./start.sh
```

This will:
- Check PostgreSQL is running
- Create `.env` from `env.example` if needed
- Start the backend API at `http://localhost:8001`
- Start the frontend at `http://localhost:3001`

Or start services manually:

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python api_server.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Database Schema

**Note:** Table names are configurable via environment variables (`USER_CONNECTIONS_TABLE` and `AUDIT_LOG_TABLE`).

### User Connections Table (default: `db_connection_infos`)

Stores user database connection information:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_email | TEXT | User's email (unique) |
| db_type | TEXT | Database type (postgres) |
| host | TEXT | Database host |
| port | INTEGER | Database port |
| db_user | TEXT | Database username |
| db_password | TEXT | Database password |
| db_name | TEXT | Database name |
| catalog_markdown | TEXT | Generated catalog |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |
| last_query_at | TIMESTAMP | Last query timestamp |
| status | TEXT | User status (active/suspended) |

## User Flow

1. **Onboard**: User enters email and PostgreSQL connection details
2. **Generate**: System connects and generates database catalog
3. **Review**: User reviews and edits the catalog with business context
4. **Save**: System stores connection info and catalog in admin DB
5. **Query**: MCP server uses email to route queries to user's database

## API Endpoints

### Backend (Port 8001)

#### Setup & Management
- `GET /health` - Health check

#### Onboarding Flow
- `POST /api/onboard/list-tables` - List all available tables in database
- `POST /api/onboard/generate` - Generate catalog from user's DB (with optional table selection)
- `POST /api/onboard/save` - Save user onboarding data
- `GET /api/onboard/status/{email}` - Check user status
- `GET /api/onboard/user/{email}` - Get complete user info (for MCP server)

### API Documentation

Interactive docs available at:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

### Table Selection Feature

Users can select specific tables when generating catalogs instead of including the entire database.

#### List Available Tables

```bash
POST /api/onboard/list-tables
```

**Request:**
```json
{
  "user_email": "user@example.com",
  "db_type": "postgres",
  "host": "localhost",
  "port": 5432,
  "db_user": "postgres",
  "db_password": "password",
  "db_name": "mydb"
}
```

**Response:**
```json
{
  "success": true,
  "tables": ["users", "orders", "products", "order_items"],
  "count": 4,
  "message": "Found 4 tables in database"
}
```

#### Generate Catalog with Table Selection

```bash
POST /api/onboard/generate
```

**Request (all tables):**
```json
{
  "user_email": "user@example.com",
  "db_type": "postgres",
  "host": "localhost",
  "port": 5432,
  "db_user": "postgres",
  "db_password": "password",
  "db_name": "mydb"
}
```

**Request (specific tables):**
```json
{
  "user_email": "user@example.com",
  "db_type": "postgres",
  "host": "localhost",
  "port": 5432,
  "db_user": "postgres",
  "db_password": "password",
  "db_name": "mydb",
  "table_names": ["users", "orders", "products"]
}
```

**Benefits:**
- Faster catalog generation for large databases
- Focused catalogs with only relevant tables
- Reduced token usage for LLM queries
- Better user experience with control over documentation

## Security Notes

⚠️ **Important for Production:**

1. **Encrypt database passwords** before storing
2. **Use HTTPS** for all connections
3. **Implement authentication** for API endpoints
4. **Add rate limiting** to prevent abuse
5. **Use environment variables** for sensitive data
6. **Implement proper key management** (AWS KMS, HashiCorp Vault)

## Integration with MCP Server

The MCP server can fetch user information using:

```python
import requests

def get_user_info(email: str):
    response = requests.get(f"http://localhost:8001/api/onboard/user/{email}")
    if response.ok:
        data = response.json()
        return {
            'connection_string': data['connection_string'],
            'catalog': data['catalog']
        }
```

## Development

### Frontend Development
```bash
cd frontend
npm run dev
```

### Backend Development
```bash
cd backend
python api_server.py
```

### Testing Database Connection
```bash
# Test if admin DB is accessible
psql postgresql://testuser:testpass@localhost:5432/onboarding_admin -c "SELECT * FROM db_connection_infos;"
```

## Troubleshooting

### Backend won't start
- Ensure PostgreSQL is running
- Verify admin database exists: `python setup_admin_db.py`
- Check connection string in environment

### Frontend can't connect to backend
- Verify backend is running on port 8001
- Check CORS settings in `api_server.py`
- Ensure no firewall blocking ports

### Catalog generation fails
- Verify user's database is accessible
- Check database credentials
- Ensure network connectivity to user's database

## Project Structure

```
onboarding_DB/
├── backend/
│   ├── api_server.py           # FastAPI application
│   ├── database_schema.sql     # Admin DB schema
│   ├── setup_admin_db.py       # Database setup script
│   ├── requirements.txt        # Python dependencies
│   └── README.md
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx           # Landing page
│   │   ├── onboard/
│   │   │   └── page.tsx       # Onboarding form
│   │   ├── review/
│   │   │   └── page.tsx       # Catalog editor
│   │   └── success/
│   │       └── page.tsx       # Success page
│   ├── package.json
│   └── README.md
│
└── README.md                  # This file
```

## Future Enhancements

- [ ] Support for MySQL, MongoDB
- [ ] Catalog versioning and history
- [ ] User dashboard with query analytics
- [ ] Email notifications
- [ ] Catalog auto-refresh on schema changes
- [ ] Team/organization support
- [ ] API key management
- [ ] Query usage metrics

