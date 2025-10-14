#!/usr/bin/env python3
"""
PostgreSQL Test Database Setup Script
Creates a test database with 4 tables and sample data for testing the catalog extractor.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import random
import sys

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'testdb',
    'user': 'testuser',
    'password': 'testpass'
}

def create_connection():
    """Create a database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def create_tables(conn):
    """Create the test tables."""
    cursor = conn.cursor()
    
    # Drop tables if they exist (in reverse order due to foreign keys)
    drop_tables = [
        "DROP TABLE IF EXISTS order_items CASCADE;",
        "DROP TABLE IF EXISTS orders CASCADE;", 
        "DROP TABLE IF EXISTS products CASCADE;",
        "DROP TABLE IF EXISTS users CASCADE;"
    ]
    
    for drop_sql in drop_tables:
        cursor.execute(drop_sql)
    
    # Create users table
    cursor.execute("""
        CREATE TABLE users (
            user_id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        );
    """)
    
    # Create products table
    cursor.execute("""
        CREATE TABLE products (
            product_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            category VARCHAR(50),
            stock_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create orders table
    cursor.execute("""
        CREATE TABLE orders (
            order_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            shipping_address TEXT
        );
    """)
    
    # Create order_items table
    cursor.execute("""
        CREATE TABLE order_items (
            order_item_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price DECIMAL(10,2) NOT NULL,
            total_price DECIMAL(10,2) NOT NULL
        );
    """)
    
    # Add some indexes
    cursor.execute("CREATE INDEX idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX idx_products_category ON products(category);")
    cursor.execute("CREATE INDEX idx_orders_user_id ON orders(user_id);")
    cursor.execute("CREATE INDEX idx_orders_status ON orders(status);")
    cursor.execute("CREATE INDEX idx_order_items_order_id ON order_items(order_id);")
    
    # Add table comments
    cursor.execute("COMMENT ON TABLE users IS 'User accounts and profile information';")
    cursor.execute("COMMENT ON TABLE products IS 'Product catalog with pricing and inventory';")
    cursor.execute("COMMENT ON TABLE orders IS 'Customer orders and order details';")
    cursor.execute("COMMENT ON TABLE order_items IS 'Individual items within each order';")
    
    # Add column comments
    cursor.execute("COMMENT ON COLUMN users.username IS 'Unique username for login';")
    cursor.execute("COMMENT ON COLUMN products.price IS 'Product price in USD';")
    cursor.execute("COMMENT ON COLUMN orders.status IS 'Order status: pending, shipped, delivered, cancelled';")
    
    conn.commit()
    print("✅ Tables created successfully")

def insert_sample_data(conn):
    """Insert sample data into the tables."""
    cursor = conn.cursor()
    
    # Sample users data
    users_data = [
        ('john_doe', 'john@example.com', 'John', 'Doe'),
        ('jane_smith', 'jane@example.com', 'Jane', 'Smith'),
        ('bob_wilson', 'bob@example.com', 'Bob', 'Wilson'),
        ('alice_brown', 'alice@example.com', 'Alice', 'Brown'),
        ('charlie_davis', 'charlie@example.com', 'Charlie', 'Davis'),
        ('diana_miller', 'diana@example.com', 'Diana', 'Miller'),
        ('eve_jones', 'eve@example.com', 'Eve', 'Jones'),
        ('frank_taylor', 'frank@example.com', 'Frank', 'Taylor'),
        ('grace_white', 'grace@example.com', 'Grace', 'White'),
        ('henry_black', 'henry@example.com', 'Henry', 'Black')
    ]
    
    cursor.executemany("""
        INSERT INTO users (username, email, first_name, last_name) 
        VALUES (%s, %s, %s, %s)
    """, users_data)
    
    # Sample products data
    products_data = [
        ('Laptop Pro 15"', 'High-performance laptop with 16GB RAM', 1299.99, 'Electronics', 25),
        ('Wireless Mouse', 'Ergonomic wireless mouse', 29.99, 'Electronics', 100),
        ('Mechanical Keyboard', 'RGB mechanical keyboard', 149.99, 'Electronics', 50),
        ('Coffee Maker', 'Automatic drip coffee maker', 89.99, 'Appliances', 30),
        ('Bluetooth Headphones', 'Noise-cancelling headphones', 199.99, 'Electronics', 40),
        ('Desk Lamp', 'LED desk lamp with dimmer', 45.99, 'Furniture', 60),
        ('Office Chair', 'Ergonomic office chair', 299.99, 'Furniture', 15),
        ('Monitor 27"', '4K 27-inch monitor', 399.99, 'Electronics', 20),
        ('Webcam HD', '1080p webcam for video calls', 79.99, 'Electronics', 35),
        ('Standing Desk', 'Adjustable height standing desk', 599.99, 'Furniture', 10)
    ]
    
    cursor.executemany("""
        INSERT INTO products (name, description, price, category, stock_quantity) 
        VALUES (%s, %s, %s, %s, %s)
    """, products_data)
    
    # Sample orders data
    orders_data = []
    statuses = ['pending', 'shipped', 'delivered', 'cancelled']
    addresses = [
        '123 Main St, New York, NY 10001',
        '456 Oak Ave, Los Angeles, CA 90210',
        '789 Pine Rd, Chicago, IL 60601',
        '321 Elm St, Houston, TX 77001',
        '654 Maple Dr, Phoenix, AZ 85001'
    ]
    
    for i in range(15):  # 15 orders
        user_id = random.randint(1, 10)
        order_date = datetime.now() - timedelta(days=random.randint(1, 30))
        status = random.choice(statuses)
        shipping_address = random.choice(addresses)
        total_amount = round(random.uniform(50.00, 500.00), 2)
        
        orders_data.append((user_id, order_date, total_amount, status, shipping_address))
    
    cursor.executemany("""
        INSERT INTO orders (user_id, order_date, total_amount, status, shipping_address) 
        VALUES (%s, %s, %s, %s, %s)
    """, orders_data)
    
    # Sample order_items data
    order_items_data = []
    
    for order_id in range(1, 16):  # 15 orders
        num_items = random.randint(1, 4)  # 1-4 items per order
        used_products = set()
        
        for _ in range(num_items):
            product_id = random.randint(1, 10)
            while product_id in used_products:
                product_id = random.randint(1, 10)
            used_products.add(product_id)
            
            quantity = random.randint(1, 3)
            # Get product price (simplified - in real app you'd query the DB)
            product_prices = [1299.99, 29.99, 149.99, 89.99, 199.99, 45.99, 299.99, 399.99, 79.99, 599.99]
            unit_price = product_prices[product_id - 1]
            total_price = round(unit_price * quantity, 2)
            
            order_items_data.append((order_id, product_id, quantity, unit_price, total_price))
    
    cursor.executemany("""
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price) 
        VALUES (%s, %s, %s, %s, %s)
    """, order_items_data)
    
    conn.commit()
    print("✅ Sample data inserted successfully")

def verify_data(conn):
    """Verify the data was inserted correctly."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Count records in each table
    tables = ['users', 'products', 'orders', 'order_items']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
        count = cursor.fetchone()['count']
        print(f"📊 {table}: {count} records")
    
    # Show some sample data
    print("\n📋 Sample Users:")
    cursor.execute("SELECT username, email, first_name, last_name FROM users LIMIT 3")
    for row in cursor.fetchall():
        print(f"  - {row['username']} ({row['email']}) - {row['first_name']} {row['last_name']}")
    
    print("\n📋 Sample Products:")
    cursor.execute("SELECT name, price, category FROM products LIMIT 3")
    for row in cursor.fetchall():
        print(f"  - {row['name']} - ${row['price']} ({row['category']})")
    
    print("\n📋 Sample Orders:")
    cursor.execute("""
        SELECT o.order_id, u.username, o.total_amount, o.status 
        FROM orders o 
        JOIN users u ON o.user_id = u.user_id 
        LIMIT 3
    """)
    for row in cursor.fetchall():
        print(f"  - Order #{row['order_id']} by {row['username']} - ${row['total_amount']} ({row['status']})")

def main():
    """Main function to set up the test database."""
    print("🚀 Setting up PostgreSQL test database...")
    print("=" * 50)
    
    # Create connection
    conn = create_connection()
    
    try:
        # Create tables
        print("📝 Creating tables...")
        create_tables(conn)
        
        # Insert sample data
        print("📦 Inserting sample data...")
        insert_sample_data(conn)
        
        # Verify data
        print("✅ Verifying data...")
        verify_data(conn)
        
        print("\n" + "=" * 50)
        print("🎉 Test database setup complete!")
        print("\nYou can now test your catalog extractor with:")
        print("python onboarding_DB/backend/catalog_extractor.py")
        print("\nConnection string:")
        print(f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        
    except Exception as e:
        print(f"❌ Error during setup: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
