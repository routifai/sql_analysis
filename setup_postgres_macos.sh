#!/bin/bash

# PostgreSQL Test Database Setup Script for macOS (Homebrew)
# This script creates the test database and user

echo "🔧 Setting up PostgreSQL test database on macOS..."

# Check if PostgreSQL is running
if ! pg_isready -q; then
    echo "❌ PostgreSQL is not running. Starting PostgreSQL..."
    brew services start postgresql
    sleep 3
fi

echo "✅ PostgreSQL is running"

# Create database and user using your current user
echo "📝 Creating database and user..."

# Create database
createdb testdb 2>/dev/null || echo "Database testdb might already exist"

# Create user (if it doesn't exist)
psql -d postgres -c "CREATE USER testuser WITH PASSWORD 'testpass';" 2>/dev/null || echo "User testuser might already exist"

# Grant privileges
psql -d testdb -c "GRANT ALL PRIVILEGES ON DATABASE testdb TO testuser;"
psql -d testdb -c "GRANT ALL ON SCHEMA public TO testuser;"
psql -d testdb -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO testuser;"
psql -d testdb -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO testuser;"
psql -d testdb -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO testuser;"
psql -d testdb -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO testuser;"

echo "✅ Database and user setup complete!"
echo ""
echo "🎉 Setup complete! You can now run:"
echo "python setup_test_db.py"
