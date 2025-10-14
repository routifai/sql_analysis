
"""
PostgreSQL Data Catalog Extractor - Corrected and Enhanced Version
Extracts schema information and generates a clean Markdown catalog
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.sql import SQL, Identifier, Literal
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
import json


class CatalogExtractor:
    """
    A class to extract metadata and sample data from a PostgreSQL database.
    """
    def __init__(self, connection_string: str):
        """Initialize the catalog extractor with a connection string."""
        self.connection_string = connection_string
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Establish a database connection and cursor."""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}", file=sys.stderr)
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the database connection and cursor."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def get_table_info(self, table_name: str, schema: str = 'public') -> Dict[str, Any]:
        """Get basic table information including description and row count."""
        try:
            # Get table comment/description
            self.cursor.execute(
                SQL("SELECT obj_description(c.oid) AS table_description FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relname = %s AND n.nspname = %s"),
                (table_name, schema)
            )
            result = self.cursor.fetchone()
            table_description = result['table_description'] if result else None

            # Get row count (approximate for large tables)
            self.cursor.execute(
                SQL("SELECT reltuples::bigint AS row_count FROM pg_class WHERE relname = %s"),
                (table_name,)
            )
            row_count = self.cursor.fetchone()['row_count']

            return {
                'name': table_name,
                'description': table_description or f"Table: {table_name}",
                'row_count': row_count
            }
        except psycopg2.Error as e:
            print(f"Error getting info for table {schema}.{table_name}: {e}", file=sys.stderr)
            return {'name': table_name, 'description': f"Error: {e}", 'row_count': -1}

    def get_all_tables(self, schema: str = 'public') -> List[str]:
        """Get a list of all tables in the schema."""
        try:
            self.cursor.execute(
                SQL("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = %s ORDER BY tablename"),
                (schema,)
            )
            return [row['tablename'] for row in self.cursor.fetchall()]
        except psycopg2.Error as e:
            print(f"Error getting tables for schema {schema}: {e}", file=sys.stderr)
            return []

    def get_columns_info(self, table_name: str, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get detailed column information."""
        try:
            self.cursor.execute(
                SQL("""
                    SELECT 
                        a.attname AS column_name,
                        pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                        a.attnotnull AS is_not_null,
                        pg_catalog.pg_get_expr(d.adbin, d.adrelid) AS column_default,
                        col_description(a.attrelid, a.attnum) AS column_description
                    FROM pg_catalog.pg_attribute a
                    LEFT JOIN pg_catalog.pg_attrdef d ON (a.attrelid, a.attnum) = (d.adrelid, d.adnum)
                    WHERE a.attrelid = (
                        SELECT c.oid FROM pg_catalog.pg_class c
                        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                        WHERE c.relname = %s AND n.nspname = %s
                    )
                    AND a.attnum > 0 AND NOT a.attisdropped
                    ORDER BY a.attnum
                """),
                (table_name, schema)
            )
            columns = []
            for row in self.cursor.fetchall():
                col_info = {
                    'name': row['column_name'],
                    'type': row['data_type'],
                    'nullable': not row['is_not_null'],
                    'default': row['column_default'],
                    'description': row['column_description'] or ''
                }
                columns.append(col_info)
            return columns
        except psycopg2.Error as e:
            print(f"Error getting columns for table {schema}.{table_name}: {e}", file=sys.stderr)
            return []

    def get_primary_key(self, table_name: str, schema: str = 'public') -> List[str]:
        """Get primary key columns."""
        try:
            self.cursor.execute(
                SQL("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = {}::regclass AND i.indisprimary
                """).format(Literal(f"{schema}.{table_name}")),
            )
            return [row['attname'] for row in self.cursor.fetchall()]
        except psycopg2.Error as e:
            print(f"Error getting PK for table {schema}.{table_name}: {e}", file=sys.stderr)
            return []

    def get_foreign_keys(self, table_name: str, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get foreign key relationships."""
        try:
            self.cursor.execute(
                SQL("""
                    SELECT
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = %s AND tc.table_name = %s
                """),
                (schema, table_name)
            )
            fks = []
            for row in self.cursor.fetchall():
                fks.append({
                    'column': row['column_name'],
                    'references_table': row['foreign_table_name'],
                    'references_column': row['foreign_column_name']
                })
            return fks
        except psycopg2.Error as e:
            print(f"Error getting FKs for table {schema}.{table_name}: {e}", file=sys.stderr)
            return []

    def get_indexes(self, table_name: str, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get table indexes."""
        try:
            self.cursor.execute(
                SQL("""
                    SELECT
                        i.relname as index_name,
                        array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS column_names,
                        ix.indisunique AS is_unique,
                        ix.indisprimary AS is_primary
                    FROM pg_class t
                    JOIN pg_index ix ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                    WHERE t.relname = %s AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)
                    GROUP BY i.relname, ix.indisunique, ix.indisprimary
                """),
                (table_name, schema)
            )
            indexes = []
            for row in self.cursor.fetchall():
                if not row['is_primary']:
                    indexes.append({
                        'name': row['index_name'],
                        'columns': row['column_names'],
                        'unique': row['is_unique']
                    })
            return indexes
        except psycopg2.Error as e:
            print(f"Error getting indexes for table {schema}.{table_name}: {e}", file=sys.stderr)
            return []

    def get_sample_data(self, table_name: str, schema: str = 'public', limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from the table, using TABLESAMPLE or a safer alternative."""
        try:
            # Safely compose the query using psycopg2.sql
            query = SQL("SELECT * FROM {}.{} TABLESAMPLE SYSTEM (1) LIMIT %s").format(
                Identifier(schema), Identifier(table_name)
            )
            self.cursor.execute(query, (limit,))
            rows = self.cursor.fetchall()

            if len(rows) < limit:
                # Use a non-random fallback for better performance on large tables
                print(f"Warning: TABLESAMPLE returned few rows. Using regular SELECT for {table_name}", file=sys.stderr)
                query = SQL("SELECT * FROM {}.{} LIMIT %s").format(
                    Identifier(schema), Identifier(table_name)
                )
                self.cursor.execute(query, (limit,))
                rows = self.cursor.fetchall()

        except psycopg2.Error as e:
            print(f"Error getting sample data for table {schema}.{table_name}: {e}", file=sys.stderr)
            return []

        return [self._serialize_row(dict(row)) for row in rows]

    def _serialize_row(self, row: Dict) -> Dict:
        """Convert row values to JSON-serializable types."""
        serialized = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value
        return serialized

    def generate_catalog(self, schema: str = 'public', table_names: Optional[List[str]] = None) -> str:
        """
        Generate a Markdown catalog for the specified schema.
        
        Args:
            schema: Database schema name (default: 'public')
            table_names: Optional list of specific table names to include.
                        If None, all tables in the schema are included.
        
        Returns:
            Markdown-formatted catalog string
        """
        markdown_output = f"# Data Catalog for Schema: `{schema}`\n\n"
        
        if table_names:
            # Use provided table names
            tables = table_names
            markdown_output += f"*Catalog generated for {len(tables)} specified table(s)*\n\n"
        else:
            # Get all tables in schema
            tables = self.get_all_tables(schema=schema)
        
        if not tables:
            return markdown_output + "No tables found or error retrieving table list.\n"
        
        for table_name in tables:
            markdown_output += f"## Table: `{table_name}`\n\n"
            
            table_info = self.get_table_info(table_name=table_name, schema=schema)
            markdown_output += f"**Description**: {table_info.get('description', '')}\n"
            markdown_output += f"**Approximate Rows**: {table_info.get('row_count', 'N/A')}\n\n"
            
            # Columns
            columns = self.get_columns_info(table_name=table_name, schema=schema)
            markdown_output += "### Columns\n"
            markdown_output += "| Column Name | Data Type | Nullable | Default | Description |\n"
            markdown_output += "|-------------|-----------|----------|---------|-------------|\n"
            for col in columns:
                markdown_output += (
                    f"| {col['name']} | {col['type']} | {col['nullable']} | {col['default'] or ''} | {col['description']} |\n"
                )
            markdown_output += "\n"
            
            # Primary Keys
            pks = self.get_primary_key(table_name=table_name, schema=schema)
            if pks:
                markdown_output += f"**Primary Key**: {', '.join(pks)}\n\n"

            # Foreign Keys
            fks = self.get_foreign_keys(table_name=table_name, schema=schema)
            if fks:
                markdown_output += "### Foreign Keys\n"
                for fk in fks:
                    markdown_output += (
                        f"- `{fk['column']}` references `{fk['references_table']}` (`{fk['references_column']}`)\n"
                    )
                markdown_output += "\n"
            
            # Indexes
            indexes = self.get_indexes(table_name=table_name, schema=schema)
            if indexes:
                markdown_output += "### Indexes\n"
                for idx in indexes:
                    unique_status = " (unique)" if idx['unique'] else ""
                    markdown_output += (
                        f"- `{idx['name']}` on columns `{', '.join(idx['columns'])}`{unique_status}\n"
                    )
                markdown_output += "\n"
            
            # Sample Data
            sample_data = self.get_sample_data(table_name=table_name, schema=schema)
            if sample_data:
                markdown_output += "### Sample Data\n"
                markdown_output += "```json\n"
                markdown_output += json.dumps(sample_data, indent=2, default=str)
                markdown_output += "\n```\n\n"
            
        return markdown_output


if __name__ == '__main__':
    # Test the catalog extractor with our test database
    connection_string = "postgresql://testuser:testpass@localhost:5432/testdb"
    
    try:
        print("🔍 Generating data catalog for test database...")
        print("=" * 60)
        
        with CatalogExtractor(connection_string) as extractor:
            catalog = extractor.generate_catalog(schema='public')
            
            # Save catalog to markdown file
            output_file = "database_catalog.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(catalog)
            
            print(f"📄 Catalog saved to: {output_file}")
            print("=" * 60)
            print("✅ Catalog generation complete!")

    except Exception as e:
        print(f"❌ An error occurred during script execution: {e}", file=sys.stderr)

