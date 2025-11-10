#!/usr/bin/env python3
"""
Main entry point for MCP servers in Azure App Service.
This script determines which MCP server to run based on the MCP_SERVER environment variable.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point to route to the correct MCP server."""
    mcp_server = os.getenv("MCP_SERVER", "").lower()
    
    if mcp_server == "ado":
        logger.info("Starting ADO MCP Server")
        from ado_mcp_stdio import main as ado_main
        import asyncio
        asyncio.run(ado_main())
    elif mcp_server == "jira":
        logger.info("Starting Jira MCP Server")
        from jira_mcp_stdio import main as jira_main
        import asyncio
        asyncio.run(jira_main())
    else:
        logger.error(f"Invalid MCP_SERVER value: '{mcp_server}'. Must be 'ado' or 'jira'")
        sys.exit(1)

if __name__ == "__main__":
    main()
