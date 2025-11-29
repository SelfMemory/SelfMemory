# MCP Server Configuration Guide

SelfMemory implements the Model Context Protocol (MCP) specification, allowing you to connect your memory system to AI applications like Claude Desktop, VS Code, and other MCP-compatible clients.

## Overview

The SelfMemory MCP server provides:

- **MCP Compliant**: Full implementation of the MCP API specification
- **OAuth 2.1 Authentication**: Secure access using RFC 9728 Protected Resource Metadata
- **Streamable HTTP Transport**: Remote server access via HTTP
- **Memory Tools**: Search and add memories through standardized MCP tools

## Server URL

**Production MCP Endpoint**: `https://mcp.selfmemory.com/mcp`

## Authentication

The SelfMemory MCP server uses OAuth 2.1 for secure authentication. The authorization flow is fully automated by MCP clients.

### Authorization Server Discovery

The server implements RFC 9728 Protected Resource Metadata, allowing clients to automatically discover:

- Authorization server endpoints
- Supported scopes
- Token requirements

**Protected Resource Metadata URL**: `https://mcp.selfmemory.com/.well-known/oauth-protected-resource`

### Required Scopes

- `memories:read` - Search and retrieve memories
- `memories:write` - Add new memories

## Client Configuration

### Claude Desktop

Add the following to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "selfmemory": {
      "url": "https://mcp.selfmemory.com/mcp",
      "type": "http"
    }
  }
}
```

After saving, restart Claude Desktop. On first use, you'll be prompted to:

1. Authorize the application through your browser
2. Log in to your SelfMemory account
3. Grant access to the requested scopes

### VS Code

1. Install the MCP extension for VS Code
2. Press `Cmd/Ctrl + Shift + P` and select **MCP: Add server...**
3. Select **HTTP** as the transport type
4. Enter the server URL: `https://mcp.selfmemory.com/mcp`
5. Give your server a name (e.g., "SelfMemory")

VS Code will handle the OAuth flow automatically when you first connect.

### Other MCP Clients

For MCP clients using the Python SDK:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def connect_to_selfmemory():
    async with streamablehttp_client("https://mcp.selfmemory.com/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")
            
            # Call a tool
            result = await session.call_tool(
                "search",
                arguments={"query": "python projects", "retrieval_limit": 5}
            )
```

For MCP clients using the TypeScript SDK:

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHttpClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const transport = new StreamableHttpClientTransport(
  new URL("https://mcp.selfmemory.com/mcp")
);

const client = new Client(
  {
    name: "selfmemory-client",
    version: "1.0.0"
  },
  {
    capabilities: {}
  }
);

await client.connect(transport);

// List tools
const tools = await client.listTools();
console.log("Available tools:", tools);

// Call a tool
const result = await client.callTool({
  name: "search",
  arguments: {
    query: "python projects",
    retrieval_limit: 5
  }
});
```

## Available Tools

### search

Search through your memories with advanced filtering.

**Parameters**:
- `query` (required): Search query string
- `retrieval_limit` (optional): Maximum results to return (default: 10)
- `tags` (optional): Filter by tags (e.g., `["work", "important"]`)
- `people_mentioned` (optional): Filter by people (e.g., `["Alice", "Bob"]`)
- `topic_category` (optional): Filter by category (e.g., `"food_preferences"`)
- `temporal_filter` (optional): Time-based filter (e.g., `"today"`, `"this_week"`)
- `threshold` (optional): Minimum similarity score (0.0-1.0)

**Example**:

```json
{
  "name": "search",
  "arguments": {
    "query": "machine learning projects",
    "retrieval_limit": 5,
    "tags": ["work", "research"]
  }
}
```

### add

Store a new memory with rich metadata.

**Parameters**:
- `content` (required): The memory content to store
- `tags` (optional): Comma-separated tags (e.g., `"work,meeting,important"`)
- `people_mentioned` (optional): Comma-separated people names (e.g., `"Alice,Bob"`)
- `topic_category` (optional): Topic category (e.g., `"food_preferences"`)
- `metadata` (optional): Additional custom metadata as key-value pairs

**Example**:

```json
{
  "name": "add",
  "arguments": {
    "content": "Discussed new ML model architecture with the team",
    "tags": "work,research,ml",
    "people_mentioned": "Sarah,Mike",
    "topic_category": "work"
  }
}
```

## Usage Examples

### In Claude Desktop

Once configured, you can use your memories naturally in conversations:

**User**: "What do I know about Python projects?"

**Claude**: *Uses the `search` tool to find relevant memories*

**User**: "Remember that I prefer using pytest for testing"

**Claude**: *Uses the `add` tool to store this preference*

### In VS Code Copilot Chat

After connecting the MCP server, use the `#` symbol to invoke tools:

```
#search machine learning notes
```

or let Copilot automatically use memories when relevant to your coding context.

## Project-Specific Memories

SelfMemory is multi-tenant and supports project isolation. Memories are automatically scoped to your selected project based on your OAuth token. To work with different projects:

1. Switch projects in the SelfMemory dashboard
2. Generate a new API key or re-authenticate
3. Your MCP client will access that project's memories

## Troubleshooting

### "Authentication failed" or "Token invalid"

- Ensure you've completed the OAuth flow in your browser
- Check that your SelfMemory account is active
- Try removing and re-adding the MCP server in your client

### "No tools available"

- Verify the server URL is correct: `https://mcp.selfmemory.com/mcp`
- Check your client's MCP configuration file
- Restart your MCP client application

### "Permission denied" errors

- Verify your OAuth token has the required scopes (`memories:read`, `memories:write`)
- Re-authorize the application to refresh permissions
- Check project access in the SelfMemory dashboard

### Connection timeouts

- Check your internet connection
- Verify the server is accessible: `curl https://mcp.selfmemory.com/.well-known/oauth-protected-resource`
- Check for firewall or proxy restrictions

## Security Considerations

1. **OAuth Tokens**: Your access tokens are stored securely by the MCP client
2. **HTTPS Only**: All communication uses encrypted HTTPS
3. **Token Validation**: Every request validates token authenticity and scope
4. **Project Isolation**: You can only access memories within your authorized projects
5. **Audience Validation**: Tokens are bound to the SelfMemory MCP server

## Advanced Configuration

### Custom Scopes

If you need to limit access, you can request specific scopes during authorization:

- `memories:read` - Read-only access to memories
- `memories:write` - Ability to create new memories

### Session Management

The server uses stateful sessions with the `Mcp-Session-Id` header. Sessions are:

- Automatically created on initialization
- Cryptographically secure
- User-specific (cannot be hijacked)
- Automatically refreshed on reconnection

### Rate Limiting

The server implements rate limiting to ensure fair usage:

- Search operations: Reasonable limits per user
- Add operations: Designed for natural usage patterns
- Automatic retry with exponential backoff recommended

## API Reference

For detailed information about the MCP protocol and specifications:

- [MCP Specification](https://modelcontextprotocol.io/specification/latest)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [SelfMemory API Documentation](https://docs.selfmemory.com)

## Support

If you encounter issues:

1. Check the [troubleshooting section](#troubleshooting) above
2. Review server logs in your MCP client
3. Visit [SelfMemory Discord](https://discord.com/invite/YypBvdUpcc)
4. Open an issue on [GitHub](https://github.com/selfmemory/selfmemory)

## Additional Resources

- [MCP Server Setup Guide](./MCP_SETUP.md) - Technical implementation details
- [OAuth Configuration](./CONFIGURATION.md) - Authentication setup
- [Python Client Usage](./Python/Client.md) - SDK integration examples
