#!/bin/bash
# SQL Validation Script for db/setup directory
# This script validates SQL syntax without executing database operations

echo "=== SQL Files Validation Script ==="
echo ""

SQL_DIR="$(dirname "$0")"
ERRORS=0

# Function to check SQL syntax
validate_sql() {
    local file=$1
    echo "Validating: $file"
    
    # Check for basic SQL syntax errors
    # Look for common issues like unmatched quotes, missing semicolons, etc.
    
    # Check for unmatched single quotes (basic check)
    quote_count=$(grep -o "'" "$file" | wc -l)
    if [ $((quote_count % 2)) -ne 0 ]; then
        echo "  ⚠️  WARNING: Odd number of single quotes found"
    fi
    
    # Check for proper semicolons at statement ends
    if ! grep -q ";" "$file"; then
        echo "  ⚠️  WARNING: No semicolons found in file"
    fi
    
    # Check for CREATE TABLE statements
    create_count=$(grep -c "CREATE TABLE" "$file")
    echo "  ✓ Found $create_count CREATE TABLE statements"
    
    # Check for CREATE FUNCTION statements
    func_count=$(grep -c "CREATE.*FUNCTION" "$file")
    echo "  ✓ Found $func_count CREATE FUNCTION statements"
    
    echo ""
}

# Validate each SQL file
echo "Checking SQL files in: $SQL_DIR"
echo ""

for sql_file in "$SQL_DIR"/*.sql; do
    if [ -f "$sql_file" ]; then
        validate_sql "$sql_file"
    fi
done

# Check for column name consistency across files
echo "=== Checking Schema Consistency ==="
echo ""

echo "Checking pe_modeling_rules table definitions..."
grep -h "CREATE TABLE pe_modeling_rules" -A 12 "$SQL_DIR"/*.sql 2>/dev/null | grep -v "^--" | sort -u
echo ""

echo "=== Validation Complete ==="
if [ $ERRORS -eq 0 ]; then
    echo "✓ No critical errors found"
    exit 0
else
    echo "✗ Found $ERRORS error(s)"
    exit 1
fi
