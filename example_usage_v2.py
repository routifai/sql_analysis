#!/usr/bin/env python3
"""
Example usage of AnalyticsSQL MCP Server v2
Demonstrates the clean architecture: Your LLM → MCP Server → Database
"""

import requests
import json

# MCP Server URL (adjust if different)
MCP_SERVER_URL = "http://localhost:8000"

def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool via HTTP"""
    response = requests.post(
        f"{MCP_SERVER_URL}/mcp",
        json={
            "tool": tool_name,
            "arguments": arguments
        }
    )
    return response.json()

def example_workflow():
    """Example workflow showing the clean architecture"""
    
    user_email = "user@example.com"
    
    print("🚀 AnalyticsSQL MCP Server v2 - Example Workflow")
    print("=" * 60)
    
    # Step 1: Get database schema for your LLM
    print("\n1️⃣ Getting database schema...")
    schema_result = call_mcp_tool("get_schema", {"user_email": user_email})
    
    if not schema_result.get("success"):
        print(f"❌ Failed to get schema: {schema_result.get('error')}")
        return
    
    print(f"✅ Schema retrieved ({schema_result['catalog_length']} characters)")
    schema_markdown = schema_result["schema"]
    
    # Step 2: Your LLM would process the natural language query
    # In this example, we'll simulate it with a simple mapping
    user_query = "Show me the top 5 users by order count"
    print(f"\n2️⃣ User query: '{user_query}'")
    
    # Step 3: Your LLM generates SQL (simulated here)
    # In reality, your LLM (Claude, GPT, etc.) would:
    # - Analyze the schema
    # - Understand the query intent
    # - Generate appropriate SQL
    sql_query = """
    SELECT u.user_id, u.username, u.email, COUNT(o.order_id) as order_count
    FROM users u
    LEFT JOIN orders o ON u.user_id = o.user_id
    GROUP BY u.user_id, u.username, u.email
    ORDER BY order_count DESC
    LIMIT 5
    """
    
    print(f"3️⃣ Generated SQL:\n{sql_query.strip()}")
    
    # Step 4: Execute the SQL via MCP server
    print("\n4️⃣ Executing SQL via MCP server...")
    execute_result = call_mcp_tool("execute_query", {
        "sql": sql_query,
        "user_email": user_email,
        "limit": 10
    })
    
    if not execute_result.get("success"):
        print(f"❌ Query failed: {execute_result.get('error')}")
        return
    
    # Step 5: Display results
    print(f"\n5️⃣ Query Results:")
    print(f"   Execution time: {execute_result['execution_time']:.3f}s")
    print(f"   Rows returned: {execute_result['row_count']}")
    print(f"   Columns: {', '.join(execute_result['columns'])}")
    
    print("\n📊 Data:")
    for i, row in enumerate(execute_result['rows'][:5], 1):
        print(f"   {i}. {row['username']} ({row['email']}) - {row['order_count']} orders")

def example_with_schema_analysis():
    """Example showing how your LLM would analyze the schema"""
    
    user_email = "user@example.com"
    
    print("\n\n🧠 LLM Schema Analysis Example")
    print("=" * 40)
    
    # Get schema
    schema_result = call_mcp_tool("get_schema", {"user_email": user_email})
    if not schema_result.get("success"):
        print(f"❌ Failed to get schema: {schema_result.get('error')}")
        return
    
    schema_markdown = schema_result["schema"]
    
    # Your LLM would analyze this schema to understand:
    print("📋 Schema Analysis (what your LLM would do):")
    print("   • Available tables: users, orders, products, order_items")
    print("   • Relationships: users → orders → order_items → products")
    print("   • Key columns: user_id, order_id, product_id")
    print("   • Date fields: created_at, order_date")
    print("   • Numeric fields: price, total_amount, quantity")
    
    # Your LLM would then generate appropriate SQL based on the query
    print("\n💡 LLM Reasoning:")
    print("   • Query: 'Show me the top 5 users by order count'")
    print("   • Need to: JOIN users with orders, GROUP BY user, COUNT orders")
    print("   • Sort by: order count DESC, LIMIT 5")

def health_check():
    """Check MCP server health"""
    print("\n\n🏥 Health Check")
    print("=" * 20)
    
    health_result = call_mcp_tool("health", {})
    
    print(f"Status: {health_result.get('status', 'unknown')}")
    print(f"Admin DB: {health_result.get('admin_database', 'unknown')}")
    print(f"Active pools: {health_result.get('active_user_pools', 0)}")
    print(f"Email auth: {health_result.get('features', {}).get('email_authentication', False)}")

if __name__ == "__main__":
    try:
        health_check()
        example_workflow()
        example_with_schema_analysis()
        
        print("\n\n✅ Example completed successfully!")
        print("\n💡 Key Benefits of v2 Architecture:")
        print("   • Your LLM has full control over text-to-SQL conversion")
        print("   • No double LLM calls (faster, cheaper)")
        print("   • You can use any LLM (Claude, GPT, local models)")
        print("   • Clean separation: LLM = reasoning, MCP = database")
        print("   • Better error handling and retry logic in your LLM")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure the MCP server is running:")
        print("python mcp_server_v2.py")
