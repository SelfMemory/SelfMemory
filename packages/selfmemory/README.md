# selfmemory

A scoped, multi-tenant knowledge wiki maintained by an agent. Raw sources are
uploaded into a scope, a sandboxed [opencode](https://opencode.ai) agent files
them into that scope's git-backed wiki, and questions are answered by the same
agent with citations.

`pip install "selfmemory[server]"` for the API (`selfmemory-api`), run worker
(`selfmemory-worker`) and MCP server (`selfmemory-mcp`).

Source, docs and architecture: https://github.com/selfmemory/selfmemory
