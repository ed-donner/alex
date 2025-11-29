"""
MCP server configurations for the Alex Researcher
"""
from agents.mcp import MCPServerStdio


def create_playwright_mcp_server(timeout_seconds=60):
    """Create a Playwright MCP server instance for web browsing.
    
    Args:
        timeout_seconds: Client session timeout in seconds (default: 60)
        
    Returns:
        MCPServerStdio instance configured for Playwright
    """
    # Base arguments
    args = [
        "@playwright/mcp@latest",
        "--headless",
        "--isolated", 
        "--no-sandbox",
        "--ignore-https-errors",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ]
    
    # Add executable path in Docker environment
    import os
    import glob
    if os.path.exists("/.dockerenv") or os.environ.get("AWS_EXECUTION_ENV"):
        # Find the installed Chrome executable dynamically
        chrome_paths = glob.glob("/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome")
        if chrome_paths:
            # Use the first (should be only one) Chrome installation found
            chrome_path = chrome_paths[0]
            print(f"DEBUG: Found Chrome at: {chrome_path}")
            args.extend(["--executable-path", chrome_path])
        else:
            # Fallback to a known path if glob doesn't find it
            print("DEBUG: Chrome not found via glob, using fallback path")
            args.extend(["--executable-path", "/root/.cache/ms-playwright/chromium-1187/chrome-linux/chrome"])
    
    params = {
        "command": "npx",
        "args": args
    }
    
    return MCPServerStdio(params=params, client_session_timeout_seconds=timeout_seconds)