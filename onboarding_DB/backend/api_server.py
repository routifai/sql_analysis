#!/usr/bin/env python3
"""
FastAPI Backend for Onboarding System
Handles catalog generation and user registration
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
from dotenv import load_dotenv
import logging
from datetime import datetime

from catalog_extractor import CatalogExtractor

# Load environment variables from parent directory (onboarding_DB/.env)
# This allows sharing .env between frontend and backend
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

# Get log level from environment (default to INFO if not set or invalid)
LOG_LEVEL_ENV = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL_NUMERIC = getattr(logging, LOG_LEVEL_ENV, logging.INFO)

# Logging configuration
logging.basicConfig(
    level=LOG_LEVEL_NUMERIC,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Text2SQL Onboarding API",
    description="API for onboarding users with their database connections",
    version="1.0.0"
)

# CORS for Next.js frontend (port 3001)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment variables
ADMIN_DB = os.getenv("ADMIN_DB_CONNECTION", "postgresql://testuser:testpass@localhost:5432/onboarding_admin")
API_PORT = int(os.getenv("API_PORT", "8001"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ============================================================================
# Pydantic Models
# ============================================================================

class DatabaseConnectionInfo(BaseModel):
    """Model for database connection information"""
    user_email: EmailStr
    db_type: str = "postgres"
    host: str
    port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    
    @validator('db_type')
    def validate_db_type(cls, v):
        if v.lower() != 'postgres':
            raise ValueError('Only postgres is supported currently')
        return v.lower()
    
    @validator('port')
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('Port must be between 1 and 65535')
        return v

class CatalogGenerateRequest(BaseModel):
    """Request model for catalog generation"""
    user_email: EmailStr
    db_type: str = "postgres"
    host: str
    port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    table_names: Optional[list[str]] = None  # Optional: specific tables to include

class CatalogSaveRequest(BaseModel):
    """Request model for saving catalog"""
    user_email: EmailStr
    catalog_markdown: str
    db_info: DatabaseConnectionInfo

class UserStatusResponse(BaseModel):
    """Response model for user status"""
    exists: bool
    email: Optional[str] = None
    onboarded_at: Optional[str] = None
    status: Optional[str] = None

# ============================================================================
# Database Utilities
# ============================================================================

def get_admin_db_connection():
    """Get connection to admin database"""
    try:
        return psycopg2.connect(ADMIN_DB)
    except Exception as e:
        logger.error(f"Failed to connect to admin DB: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def build_connection_string(db_info: DatabaseConnectionInfo) -> str:
    """Build PostgreSQL connection string from db_info"""
    return f"postgresql://{db_info.db_user}:{db_info.db_password}@{db_info.host}:{db_info.port}/{db_info.db_name}"

def test_database_connection(connection_string: str) -> tuple[bool, str]:
    """Test if database connection is valid"""
    try:
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return True, version
    except Exception as e:
        return False, str(e)

def log_audit(user_email: str, action: str, details: dict = None):
    """Log audit event"""
    try:
        conn = get_admin_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO onboarding_audit_log (user_email, action, details)
            VALUES (%s, %s, %s)
        """, (user_email, action, psycopg2.extras.Json(details or {})))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Text2SQL Onboarding API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "test_connection": "/api/onboard/test-connection",
            "list_tables": "/api/onboard/list-tables",
            "generate_catalog": "/api/onboard/generate",
            "save_onboarding": "/api/onboard/save",
            "check_user": "/api/onboard/status/{email}"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        conn = get_admin_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/onboard/test-connection")
async def test_connection(request: DatabaseConnectionInfo):
    """
    Test database connection (heartbeat check)
    Verifies credentials and connectivity without extracting schema
    """
    try:
        logger.info(f"🔌 Testing connection for {request.user_email}")
        
        # Build connection string
        connection_string = build_connection_string(request)
        
        # Test connection
        is_valid, message = test_database_connection(connection_string)
        
        if not is_valid:
            logger.error(f"❌ Connection test failed: {message}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot connect to database: {message}"
            )
        
        logger.info(f"✅ Connection test successful")
        
        # Log audit
        log_audit(request.user_email, 'connection_tested', {
            'db_host': request.host,
            'db_name': request.db_name,
            'success': True
        })
        
        return {
            "success": True,
            "message": "Database connection successful!",
            "db_version": message,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}", exc_info=True)
        
        # Log audit for failed attempts
        log_audit(request.user_email, 'connection_test_failed', {
            'db_host': request.host,
            'db_name': request.db_name,
            'error': str(e)
        })
        
        raise HTTPException(
            status_code=500, 
            detail=f"Connection test failed: {str(e)}"
        )

@app.post("/api/onboard/list-tables")
async def list_tables(request: CatalogGenerateRequest):
    """
    List all tables in the database for user selection
    """
    try:
        logger.info(f"📋 Listing tables for {request.user_email}")
        
        # Build connection string
        connection_string = f"postgresql://{request.db_user}:{request.db_password}@{request.host}:{request.port}/{request.db_name}"
        
        # Test connection first
        is_valid, message = test_database_connection(connection_string)
        if not is_valid:
            logger.error(f"❌ Connection failed: {message}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot connect to database: {message}"
            )
        
        # Get list of tables
        with CatalogExtractor(connection_string) as extractor:
            tables = extractor.get_all_tables(schema='public')
        
        logger.info(f"✅ Found {len(tables)} tables")
        
        return {
            "success": True,
            "tables": tables,
            "count": len(tables),
            "message": f"Found {len(tables)} tables in database"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")

@app.post("/api/onboard/generate")
async def generate_catalog(request: CatalogGenerateRequest):
    """
    Step 1: Generate catalog from user's database
    Validates connection and extracts schema
    """
    try:
        logger.info(f"📋 Generating catalog for {request.user_email}")
        
        # Build connection string
        connection_string = f"postgresql://{request.db_user}:{request.db_password}@{request.host}:{request.port}/{request.db_name}"
        
        # Test connection first
        is_valid, message = test_database_connection(connection_string)
        if not is_valid:
            logger.error(f"❌ Connection failed: {message}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot connect to database: {message}"
            )
        
        logger.info(f"✅ Database connection successful")
        
        # Generate catalog using the existing CatalogExtractor
        with CatalogExtractor(connection_string) as extractor:
            # Validate table names if provided
            if request.table_names:
                all_tables = extractor.get_all_tables(schema='public')
                invalid_tables = [t for t in request.table_names if t not in all_tables]
                
                if invalid_tables:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid table names: {', '.join(invalid_tables)}. Available tables: {', '.join(all_tables)}"
                    )
                
                logger.info(f"🔍 Extracting schema for {len(request.table_names)} specific tables: {', '.join(request.table_names)}")
            else:
                logger.info(f"🔍 Extracting schema for all tables...")
            
            catalog = extractor.generate_catalog(schema='public', table_names=request.table_names)
        
        logger.info(f"✅ Catalog generated: {len(catalog)} characters")
        
        # Log audit
        log_audit(request.user_email, 'catalog_generated', {
            'db_host': request.host,
            'db_name': request.db_name,
            'catalog_length': len(catalog),
            'table_names': request.table_names,
            'table_count': len(request.table_names) if request.table_names else 'all'
        })
        
        return {
            "success": True,
            "email": request.user_email,
            "catalog": catalog,
            "db_version": message,
            "message": "Catalog generated successfully. Please review and save."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Catalog generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Catalog generation failed: {str(e)}")

@app.post("/api/onboard/save")
async def save_onboarding(request: CatalogSaveRequest):
    """
    Step 2: Save user onboarding information to admin database
    Stores connection info and catalog
    """
    try:
        logger.info(f"💾 Saving onboarding for {request.user_email}")
        
        conn = get_admin_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Insert or update user information
        cursor.execute("""
            INSERT INTO db_connection_infos (
                user_email, db_type, host, port, db_user, db_password, 
                db_name, catalog_markdown, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_email) 
            DO UPDATE SET 
                db_type = EXCLUDED.db_type,
                host = EXCLUDED.host,
                port = EXCLUDED.port,
                db_user = EXCLUDED.db_user,
                db_password = EXCLUDED.db_password,
                db_name = EXCLUDED.db_name,
                catalog_markdown = EXCLUDED.catalog_markdown,
                updated_at = NOW()
            RETURNING user_email, created_at, updated_at
        """, (
            request.user_email,
            request.db_info.db_type,
            request.db_info.host,
            request.db_info.port,
            request.db_info.db_user,
            request.db_info.db_password,
            request.db_info.db_name,
            request.catalog_markdown
        ))
        
        result = cursor.fetchone()
        conn.commit()
        
        # Log audit
        log_audit(request.user_email, 'onboarding_complete', {
            'catalog_length': len(request.catalog_markdown)
        })
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ User {request.user_email} onboarded successfully")
        
        return {
            "success": True,
            "email": request.user_email,
            "onboarded_at": result['created_at'].isoformat() if result['created_at'] else result['updated_at'].isoformat(),
            "message": "Onboarding complete! You can now use the MCP server with your email."
        }
        
    except Exception as e:
        logger.error(f"❌ Save failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save onboarding: {str(e)}")

@app.get("/api/onboard/status/{email}")
async def check_user_status(email: str):
    """
    Check if user is onboarded and get their status
    """
    try:
        conn = get_admin_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT user_email, created_at, updated_at, status, last_query_at, db_type, host, db_name
            FROM db_connection_infos
            WHERE user_email = %s
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            return {
                "exists": True,
                "email": user['user_email'],
                "onboarded_at": user['created_at'].isoformat(),
                "updated_at": user['updated_at'].isoformat() if user['updated_at'] else None,
                "status": user['status'],
                "last_query": user['last_query_at'].isoformat() if user['last_query_at'] else None,
                "db_info": {
                    "type": user['db_type'],
                    "host": user['host'],
                    "database": user['db_name']
                }
            }
        else:
            return {"exists": False}
            
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/onboard/user/{email}")
async def get_user_info(email: str):
    """
    Get complete user information including connection details and catalog
    Used by MCP server to route queries
    """
    try:
        conn = get_admin_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT *
            FROM db_connection_infos
            WHERE user_email = %s AND status = 'active'
        """, (email,))
        
        user = cursor.fetchone()
        
        if user:
            # Update last_query_at
            cursor.execute("""
                UPDATE db_connection_infos
                SET last_query_at = NOW()
                WHERE user_email = %s
            """, (email,))
            conn.commit()
        
        cursor.close()
        conn.close()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found or not active")
        
        return {
            "success": True,
            "user_email": user['user_email'],
            "db_type": user['db_type'],
            "host": user['host'],
            "port": user['port'],
            "db_user": user['db_user'],
            "db_password": user['db_password'],
            "db_name": user['db_name'],
            "catalog": user['catalog_markdown'],
            "connection_string": f"postgresql://{user['db_user']}:{user['db_password']}@{user['host']}:{user['port']}/{user['db_name']}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get user info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 80)
    logger.info("🚀 Text2SQL Onboarding API Server")
    logger.info(f"🌍 Environment: {ENVIRONMENT}")
    logger.info(f"📊 Admin DB: {ADMIN_DB}")
    logger.info(f"🔍 Log Level: {LOG_LEVEL_ENV}")
    logger.info(f"🌐 Server: http://0.0.0.0:{API_PORT}")
    logger.info(f"📖 Docs: http://0.0.0.0:{API_PORT}/docs")
    logger.info("=" * 80)
    
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level=LOG_LEVEL_ENV.lower())

