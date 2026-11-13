"""Compatibilidad entre mcp 1.x (FastMCP) y mcp 2.x (MCPServer)."""
try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server

__all__ = ["Server"]
