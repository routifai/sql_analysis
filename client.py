#!/usr/bin/env python3
"""
Text-to-SQL MCP Client with Streamable HTTP
Interactive client using OpenAI to chat with database via natural language
"""

import asyncio
import json
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError

# Import your centralized LLM client
from llm_client import get_llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Text2SQLClient:
    """Interactive Text-to-SQL client using OpenAI with MCP tools"""
    
    def __init__(self, server_url: str = "http://localhost:8000/mcp"):
        self.server_url = server_url
        
        # Use centralized LLM configuration
        self.llm_client = get_llm_client()
        self.openai_client = self.llm_client.get_async_client()
        self.model = self.llm_client.model
        
        logger.info(f"Text-to-SQL Client initialized with model: {self.model}")
    
    async def chat_with_database(self, user_message: str) -> str:
        """Chat with database using natural language"""
        try:
            async with streamablehttp_client(self.server_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Get available tools
                    tools_response = await session.list_tools()
                    
                    # Convert MCP tools to OpenAI format
                    openai_tools = []
                    for tool in tools_response.tools:
                        openai_function = {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema or {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                }
                            }
                        }
                        openai_tools.append(openai_function)
                    
                    logger.info(f"📋 Loaded {len(openai_tools)} database tools")
                    
                    # Create system prompt for database queries
                    messages = [
                        {
                            "role": "system",
                            "content": """You are a helpful database assistant with access to analytics data.

Available tools:
- text_to_sql: Convert natural language questions to SQL and execute them (auto-fixes errors)
- get_schema: View complete database schema
- health: Check database connection status

When users ask data questions:
1. Use text_to_sql tool with their EXACT question
2. DO NOT modify or rephrase their query
3. Present results in a clear, formatted way
4. If they ask about available data, use get_schema first

Examples:
- "How many users are in Finance?" → Use text_to_sql
- "Show top 10 users by usage" → Use text_to_sql
- "What tables do we have?" → Use get_schema
- "Is the database connected?" → Use health

Be helpful and conversational. Format data results as tables when appropriate."""
                        },
                        {
                            "role": "user",
                            "content": user_message
                        }
                    ]
                    
                    # First OpenAI call
                    response = await self.openai_client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                        max_tokens=2000
                    )
                    
                    response_message = response.choices[0].message
                    messages.append(response_message)
                    
                    # Check if tools were called
                    if response_message.tool_calls:
                        print(f"\n🔧 Using tools: {[tc.function.name for tc in response_message.tool_calls]}")
                        
                        for tool_call in response_message.tool_calls:
                            tool_name = tool_call.function.name
                            tool_args = json.loads(tool_call.function.arguments)
                            
                            print(f"📞 Calling '{tool_name}' with: {tool_args}")
                            
                            try:
                                # Call MCP tool
                                result = await session.call_tool(tool_name, tool_args)
                                
                                if result.content and len(result.content) > 0:
                                    content = result.content[0]
                                    tool_result = content.text if hasattr(content, 'text') else str(content)
                                else:
                                    tool_result = "No response from tool"
                                
                                # Parse JSON result for better display
                                try:
                                    parsed = json.loads(tool_result)
                                    if parsed.get('success'):
                                        print(f"✅ Query successful: {parsed.get('row_count', 0)} rows")
                                        if 'sql' in parsed:
                                            print(f"📝 SQL: {parsed['sql'][:100]}...")
                                    else:
                                        print(f"❌ Query failed: {parsed.get('error', 'Unknown error')}")
                                except:
                                    pass
                                
                                # Add to messages
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": tool_result
                                })
                                
                            except McpError as e:
                                logger.error(f"MCP Error: {e}")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": f"Error: {e}"
                                })
                        
                        # Get final response from OpenAI
                        final_response = await self.openai_client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            max_tokens=2000
                        )
                        
                        return final_response.choices[0].message.content
                    else:
                        # Direct response without tools
                        return response_message.content
                        
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.exception("Chat error details:")
            return f"Error: {e}"
    
    async def test_connection(self) -> bool:
        """Test connections to LLM and MCP server"""
        try:
            # Test LLM
            if not self.llm_client.is_available():
                logger.error("LLM not available")
                return False
            
            # Test MCP server
            async with streamablehttp_client(self.server_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    logger.info(f"✅ Connected to MCP server: {len(tools.tools)} tools available")
            
            return True
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


async def main():
    """Main interactive chat"""
    print("=" * 60)
    print("🗄️  Text-to-SQL Interactive Client")
    print("=" * 60)
    
    # Test LLM connection
    try:
        llm_client = get_llm_client()
        if not llm_client.test_connection():
            print("❌ Failed to connect to LLM. Check your API key.")
            return
        
        print("✅ LLM connection successful!")
        
        # Show LLM config
        print(f"🔗 Using: OpenAI ({llm_client.model})")
        
        # Create client
        client = Text2SQLClient()
        
        # Test MCP server
        if not await client.test_connection():
            print("❌ MCP server not reachable. Start the server first:")
            print("   python server.py")
            return
        
        print("✅ Text-to-SQL MCP server connected!")
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return
    
    print("\n" + "=" * 60)
    print("🤖 Ready! Ask questions about your database in plain English.")
    print("=" * 60)
    print("\n💡 Example questions:")
    print("   • How many users do we have?")
    print("   • Show me the top 10 users by usage time")
    print("   • What's the average session duration by department?")
    print("   • How many users are in Finance?")
    print("   • Show me users who haven't logged in for 30 days")
    print("   • What tables are available? (uses get_schema)")
    print("\n🛑 Type 'quit', 'exit', or 'bye' to exit")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye!")
                break
            
            # Special commands
            if user_input.lower() == 'help':
                print("\n📚 Available commands:")
                print("   • Ask any question about the database")
                print("   • 'schema' or 'tables' - View database structure")
                print("   • 'health' - Check database connection")
                print("   • 'quit' - Exit")
                continue
            
            if user_input.lower() in ['schema', 'tables']:
                user_input = "Show me the database schema"
            
            if user_input.lower() == 'health':
                user_input = "Check database health"
            
            # Get response
            print("\n🔄 Processing...")
            response = await client.chat_with_database(user_input)
            
            print(f"\n🤖 Assistant:\n{response}")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.exception("Main loop error:")
            print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())