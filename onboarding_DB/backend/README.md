# Onboarding Backend API

FastAPI backend for the Text2SQL onboarding system.

## Setup

### 1. Install Dependencies

```bash
cd onboarding_DB/backend
pip install -r requirements.txt
```

### 2. Configure Environment

**Note:** The backend uses a shared `.env` file located at `onboarding_DB/.env` (not in the backend directory).

If you haven't already, create the environment file:

```bash
cd ..  # Go to onboarding_DB directory
cp env.example .env
```

Edit `onboarding_DB/.env` and set your configuration:

```env
# Backend Configuration
ADMIN_DB_CONNECTION=postgresql://testuser:testpass@localhost:5432/onboarding_admin
API_PORT=8001
ENVIRONMENT=development
LOG_LEVEL=INFO

# Frontend Configuration
NEXT_PUBLIC_API_URL=http://localhost:8001
PORT=3001
```

This single `.env` file is shared by both frontend and backend.

### 3. Create Admin Database

The admin database stores user connection information and catalogs:

```bash
cd backend
python setup_admin_db.py
```

This will:
- Create the `onboarding_admin` database
- Create the `db_connection_infos` table
- Create the `onboarding_audit_log` table
- Set up proper permissions

### 4. Start the API Server

```bash
python api_server.py
```

The API will be available at: `http://localhost:8001`

Or use the startup script from the `onboarding_DB` directory:
```bash
cd ..
./start.sh  # Starts both backend and frontend
```

API documentation:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ADMIN_DB_CONNECTION` | PostgreSQL connection string for admin DB | `postgresql://testuser:testpass@localhost:5432/onboarding_admin` | Yes |
| `API_PORT` | Port for the API server | `8001` | No |
| `ENVIRONMENT` | Environment (development/staging/production) | `development` | No |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` | No |

## API Endpoints

### Health Check
```bash
GET /health
```

### List Available Tables
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

### Generate Catalog
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

### Save Onboarding
```bash
POST /api/onboard/save
```

**Request:**
```json
{
  "user_email": "user@example.com",
  "catalog_markdown": "# Generated catalog...",
  "db_info": {
    "user_email": "user@example.com",
    "db_type": "postgres",
    "host": "localhost",
    "port": 5432,
    "db_user": "username",
    "db_password": "password",
    "db_name": "database"
  }
}
```

### Check User Status
```bash
GET /api/onboard/status/{email}
```

### Get User Info (for MCP server)
```bash
GET /api/onboard/user/{email}
```

## Troubleshooting

### "Admin database connection failed"
- Verify PostgreSQL is running: `pg_isready`
- Check `ADMIN_DB_CONNECTION` in `onboarding_DB/.env` (parent directory)
- Ensure the `onboarding_admin` database exists
- Run `python setup_admin_db.py` to create it

### "Module not found" errors
- Ensure you're in the correct directory
- Install dependencies: `pip install -r requirements.txt`
- Use a virtual environment (recommended)

### Port 8001 already in use
- Change `API_PORT` in `onboarding_DB/.env`
- Or kill the process using port 8001:
  ```bash
  lsof -ti:8001 | xargs kill -9
  ```

### CORS errors from frontend
- Ensure frontend is running on port 3001
- Check CORS configuration in `api_server.py`
- Verify `NEXT_PUBLIC_API_URL` in `.env` matches backend URL

### ".env file not found" errors
- The backend loads `.env` from the parent directory (`onboarding_DB/.env`)
- Ensure `onboarding_DB/.env` exists (not `backend/.env`)
- Copy from `env.example`: `cp ../env.example ../.env`

## Development

### Running in Development Mode

```bash
# With auto-reload
uvicorn api_server:app --reload --port 8001
```

### Testing the API

```bash
# Health check
curl http://localhost:8001/health

# Test catalog generation
curl -X POST http://localhost:8001/api/onboard/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_email": "test@example.com",
    "db_type": "postgres",
    "host": "localhost",
    "port": 5432,
    "db_user": "testuser",
    "db_password": "testpass",
    "db_name": "testdb"
  }'
```

## Database Schema

The admin database contains:

### `db_connection_infos` Table
Stores user database connection information and catalogs.

### `onboarding_audit_log` Table
Tracks all onboarding events for auditing purposes.

See `database_schema.sql` for the complete schema.

