#!/bin/bash

# Grant testuser permission to create databases
# This needs to be run if setup_admin_db.py fails with permission error

echo "🔐 Granting database creation permissions to testuser..."
echo "=================================================="
echo ""

# Try to connect as postgres and grant permissions
psql -U postgres -c "ALTER USER testuser CREATEDB;" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Successfully granted CREATEDB permission to testuser"
    echo ""
    echo "Now you can run: python setup_admin_db.py"
else
    echo "❌ Failed to connect as postgres user"
    echo ""
    echo "Please try one of these alternatives:"
    echo ""
    echo "1. If you're on macOS and installed via Homebrew:"
    echo "   psql postgres -c \"ALTER USER testuser CREATEDB;\""
    echo ""
    echo "2. If postgres has a password:"
    echo "   psql -U postgres -W -c \"ALTER USER testuser CREATEDB;\""
    echo ""
    echo "3. Or create the database manually:"
    echo "   psql -U postgres -c \"CREATE DATABASE onboarding_admin OWNER testuser;\""
fi

