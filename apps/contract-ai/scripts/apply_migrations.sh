#!/bin/bash
# Script to apply database migrations

set -e  # Exit on error

echo "🗄️  Applying database migrations..."
echo

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set, using default from alembic.ini"
fi

# Show current migration status
echo "📋 Current migration status:"
alembic current
echo

# Show pending migrations
echo "📋 Pending migrations:"
alembic heads
echo

# Apply migrations
echo "🚀 Applying migrations..."
alembic upgrade head

echo
echo "✅ Migrations applied successfully!"
echo

# Show new status
echo "📋 New migration status:"
alembic current
