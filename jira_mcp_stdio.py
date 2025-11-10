#!/usr/bin/env python3
"""
Jira MCP Server implementing the Model Context Protocol for AI Toolkit integration.
This server communicates via JSON-RPC over stdin/stdout as required by AI Toolkit.
"""

import asyncio
import json
import sys
import os
import logging
import requests
import threading
import time
import webbrowser
from typing import Dict, List, Any, Optional
from flask import Flask, request, redirect, jsonify
from urllib.parse import urlencode

# Add the parent directory to the path so we can import our existing server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging to stderr (not stdout to avoid interfering with MCP protocol)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

def safe_call(tool_func, *args, **kwargs):
    """
    Helper function that adds a 2-second wait before executing tool functions
    to prevent rate-limit issues with Jira API.
    """
    func_name = getattr(tool_func, '__name__', str(tool_func))
    logger.info(f"Waiting 2 seconds before calling {func_name}")
    time.sleep(2)
    logger.info(f"Executing {func_name}")
    return tool_func(*args, **kwargs)

async def async_safe_call(tool_func, *args, **kwargs):
    """
    Async helper function that adds a 2-second wait before executing async tool functions
    to prevent rate-limit issues with Jira API.
    """
    func_name = getattr(tool_func, '__name__', str(tool_func))
    logger.info(f"Waiting 2 seconds before calling {func_name}")
    time.sleep(2)  # Using time.sleep instead of asyncio.sleep to ensure blocking
    logger.info(f"Executing {func_name}")
    return await tool_func(*args, **kwargs)

class OAuthTokenManager:
    """Manages OAuth 2.0 tokens for Jira authentication."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:9000/oauth/callback"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.auth_url = "https://auth.atlassian.com/authorize"
        self.token_url = "https://auth.atlassian.com/oauth/token"
        

        
        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.cloud_id = None
        self.expires_at = None
        
        # OAuth flow management
        self.oauth_app = None
        self.oauth_thread = None
        self.auth_complete = threading.Event()
        
    def start_oauth_flow(self) -> str:
        """Start the OAuth flow and return the authorization URL."""
    
        self._start_oauth_server()
        
        # Build authorization URL with comprehensive scopes matching admin-granted permissions
        params = {
            'audience': 'api.atlassian.com',
            'client_id': self.client_id,
            'scope': 'read:jira-work write:jira-work write:project:jira read:jira-user manage:jira-project manage:jira-configuration offline_access',
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'prompt': 'consent'
        }
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        
        logger.info(f"Opening browser for OAuth authorization: {auth_url}")
        
        # Open browser automatically
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            logger.warning(f"Could not open browser automatically: {e}")
            logger.info(f"Please manually open this URL in your browser: {auth_url}")
        
        return auth_url
    
    def _start_oauth_server(self):
        """Start the Flask server for OAuth callback."""
        if self.oauth_thread and self.oauth_thread.is_alive():
            return
            
        self.oauth_app = Flask(__name__)
        self.oauth_app.logger.disabled = True
        
        @self.oauth_app.route('/oauth/callback')
        def oauth_callback():
            code = request.args.get('code')
            error = request.args.get('error')
            
            if error:
                logger.error(f"OAuth error: {error}")
                self.auth_complete.set()
                return "OAuth failed. Please check the logs."
            
            if code:
                logger.info("Received authorization code, exchanging for tokens...")
                success = self._exchange_code_for_tokens(code)
                if success:
                    self.auth_complete.set()
                    return "OAuth successful! You can close this window."
                else:
                    self.auth_complete.set()
                    return "OAuth failed during token exchange. Please check the logs."
            
            return "Invalid callback"
        
        def run_server():
            if self.oauth_app:
                self.oauth_app.run(host='localhost', port=9000, debug=False, use_reloader=False)
        
        self.oauth_thread = threading.Thread(target=run_server, daemon=True)
        self.oauth_thread.start()
        
        # Give the server a moment to start
        time.sleep(1)
    
    def _exchange_code_for_tokens(self, code: str) -> bool:
        """Exchange authorization code for access and refresh tokens."""
        try:
            payload = {
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'redirect_uri': self.redirect_uri
            }
            
            response = requests.post(self.token_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens.get('access_token')
                self.refresh_token = tokens.get('refresh_token')
                expires_in = tokens.get('expires_in', 3600)
                self.expires_at = time.time() + expires_in - 300  # Refresh 5 minutes early
                
                # Get cloud ID
                self._get_cloud_id()
                
                # DO NOT save tokens for session-based authentication
                
                logger.info("OAuth tokens obtained successfully")
                return True
            else:
                logger.error(f"Token exchange failed: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return False
    
    def _get_cloud_id(self):
        """Get the Atlassian cloud ID for API calls."""
        try:
            if not self.access_token:
                return False
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }
            
            response = requests.get('https://api.atlassian.com/oauth/token/accessible-resources', headers=headers, timeout=15)
            
            if response.status_code == 200:
                resources = response.json()
                if resources:
                    self.cloud_id = resources[0]['id']
                    logger.info(f"Cloud ID obtained: {self.cloud_id}")
                    return True
                else:
                    logger.error("No accessible resources found")
            else:
                logger.error(f"Failed to get cloud resources: {response.status_code} {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting cloud ID: {e}")
            
        return False
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        try:
            if not self.refresh_token:
                logger.error("No refresh token available")
                return False
            
            payload = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token
            }
            
            response = requests.post(self.token_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens.get('access_token')
                
                # Update refresh token if provided
                if 'refresh_token' in tokens:
                    self.refresh_token = tokens['refresh_token']
                
                expires_in = tokens.get('expires_in', 3600)
                self.expires_at = time.time() + expires_in - 300
                
                # DO NOT save refreshed tokens for session-based authentication
                        
                logger.info("Access token refreshed successfully")
                return True
            else:
                logger.error(f"Token refresh failed: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        if not self.access_token:
            return None
        
        # Check if token is expired
        if self.expires_at and time.time() >= self.expires_at:
            logger.info("Access token expired, refreshing...")
            if not self.refresh_access_token():
                return None
        
        return self.access_token
    
    def wait_for_authorization(self, timeout: int = 300) -> bool:
        """Wait for OAuth authorization to complete."""
        return self.auth_complete.wait(timeout)
    
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication."""
        return bool(self.access_token and self.cloud_id)
    
    def _clear_tokens(self):
        """Clear all session tokens."""
        self.access_token = None
        self.refresh_token = None
        self.cloud_id = None
        self.expires_at = None

class JiraMCPServer:
    """Jira MCP Server implementing Model Context Protocol with OAuth 2.0 authentication."""
    
    def __init__(self):
        # OAuth credentials (required)
        self.oauth_manager = None
        self.auth_method = None
        self.session_authenticated = False  # Track session authentication status
        
        client_id = os.getenv("ATLASSIAN_CLIENT_ID")
        client_secret = os.getenv("ATLASSIAN_CLIENT_SECRET")
        
        if not (client_id and client_secret):
            logger.error("OAuth credentials (ATLASSIAN_CLIENT_ID/SECRET) are required")
            sys.exit(1)
        
        # Initialize OAuth
        self.oauth_manager = OAuthTokenManager(client_id, client_secret)
        logger.info("OAuth credentials configured, OAuth authentication available")
            
        logger.info(f"Initialized Jira MCP Server with OAuth 2.0 support")
    
    def _get_auth_headers(self) -> Optional[Dict[str, str]]:
        """Get authentication headers for API calls."""
        if self.oauth_manager and self.oauth_manager.is_authenticated():
            token = self.oauth_manager.get_valid_token()
            if token:
                return {
                    'Authorization': f'Bearer {token}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
        
        return None
    
    def _get_base_url(self) -> Optional[str]:
        """Get the base URL for Jira API calls."""
        if self.oauth_manager and self.oauth_manager.is_authenticated():
            return f"https://api.atlassian.com/ex/jira/{self.oauth_manager.cloud_id}"
        
        return None
    
    def _get_auth(self):
        """Get auth method for requests."""
        if self.oauth_manager and self.oauth_manager.is_authenticated():
            return None  # Headers handle OAuth
        
        return None
    
    async def _authenticate_if_needed(self) -> bool:
        """Authenticate once per session if not already authenticated."""
        # If already authenticated in this session, return True
        if self.session_authenticated:
            logger.info("Session already authenticated, using existing authentication")
            return True
            
        if self.oauth_manager:
            # Start fresh OAuth flow for new session
            logger.info("Starting OAuth authentication flow for new session...")
            
            auth_url = self.oauth_manager.start_oauth_flow()
            
            logger.info("Waiting for user authorization...")
            if self.oauth_manager.wait_for_authorization(timeout=300):  # 5 minutes timeout
                if self.oauth_manager.is_authenticated():
                    self.auth_method = "oauth"
                    self.session_authenticated = True  # Mark session as authenticated
                    logger.info("✅ OAuth authentication successful - session established")
                    return True
                else:
                    logger.error("❌ OAuth authentication failed")
            else:
                logger.error("❌ OAuth authentication timed out")
            
        return False

    def clear_session(self):
        """Clear OAuth session and tokens after work item creation completion."""
        logger.info("Clearing OAuth session and tokens...")
        
        if self.oauth_manager:
            # Clear OAuth tokens
            self.oauth_manager._clear_tokens()
            
        # Reset session state
        self.session_authenticated = False
        self.auth_method = None
        
        logger.info("✅ OAuth session cleared successfully")

    async def handle_initialize(self, params: Dict) -> Dict:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "jira-mcp-server",
                "version": "1.0.0"
            }
        }
    
    async def handle_tools_list(self, params: Dict) -> Dict:
        """Handle tools/list request with context-aware descriptions."""
        return {
            "tools": [
                {
                    "name": "authenticate",
                    "description": "Authenticate with Jira using OAuth 2.0 - REQUIRED FIRST",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_all_projects",
                    "description": "Get all Jira projects - Use ONLY for project discovery and conflict checking",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "create_project",
                    "description": "Create a new Jira project - Use ONLY when new project needed", 
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "projectKey": {"type": "string"},
                            "projectName": {"type": "string"},
                            "projectType": {"type": "string", "default": "software"}
                        },
                        "required": ["projectKey", "projectName"]
                    }
                },
                {
                    "name": "get_issue_types",
                    "description": "Get available issue types - Use ONCE per project for hierarchy planning",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"}
                        },
                        "required": ["project"]
                    }
                },
                {
                    "name": "create_issue",
                    "description": "Create work items with parent relationships - PRIMARY creation tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "issueType": {"type": "string", "default": "Task"},
                            "parent_id": {"type": "string"},
                            "priority": {"type": "string"},
                            "labels": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["project", "title"]
                    }
                },
                {
                    "name": "update_issue",
                    "description": "Update existing issues - Use ONLY if create_issue parent linking failed",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "issueKey": {"type": "string"},
                            "fields": {"type": "object"}
                        },
                        "required": ["issueKey", "fields"]
                    }
                },
                {
                    "name": "get_issue",
                    "description": "Get specific issue details - Use ONLY for verification after creation errors",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "issueKey": {"type": "string"}
                        },
                        "required": ["issueKey"]
                    }
                },
                {
                    "name": "search_issues",
                    "description": "for existing issues - Use ONLY if user requests finding existing items",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"},
                            "jql": {"type": "string"}
                        },
                        "required": ["project"]
                    }
                },
                {
                    "name": "clear_session",
                    "description": "Clear OAuth session - REQUIRED at end of BRD processing",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]
        }
    
    async def handle_tools_call(self, params: Dict) -> Dict:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Calling tool: {tool_name} with args: {arguments}")
        
        try:
            if tool_name == "authenticate":
                return await async_safe_call(self._authenticate)
            elif tool_name == "get_all_projects":
                return await async_safe_call(self._get_all_projects)
            elif tool_name == "create_project":
                return await async_safe_call(self._create_project, arguments)
            elif tool_name == "create_issue":
                return await async_safe_call(self._create_issue, arguments)
            elif tool_name == "get_issue_types":
                return await async_safe_call(self._get_issue_types, arguments)
            elif tool_name == "search_issues":
                return await async_safe_call(self._search_issues, arguments)
            elif tool_name == "get_issue":
                return await async_safe_call(self._get_issue, arguments)
            elif tool_name == "update_issue":
                return await async_safe_call(self._update_issue, arguments)
            elif tool_name == "clear_session":
                return await async_safe_call(self._clear_session)
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Unknown tool: {tool_name}"
                        }
                    ],
                    "isError": True
                }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing {tool_name}: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    def _make_api_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated API request to Jira."""
        headers = self._get_auth_headers()
        base_url = self._get_base_url()
        auth = self._get_auth()
        
        if not base_url:
            raise Exception("No valid Jira URL configured")
        
        url = f"{base_url}/rest/api/3{endpoint}"
        
        # Set up request parameters
        request_kwargs = kwargs.copy()
        
        if headers:
            # OAuth - use headers
            request_kwargs['headers'] = headers
        elif auth:
            # Basic Auth - use auth
            request_kwargs['auth'] = auth
        else:
            raise Exception("No valid authentication method available")
        
        # Make the request
        return requests.request(method, url, **request_kwargs)
    
    async def _authenticate(self) -> Dict:
        """Handle authentication tool call - always force fresh OAuth."""
        # Force fresh OAuth authentication for each session
        if await self._authenticate_if_needed():
            auth_status = "OAuth 2.0" if self.auth_method == "oauth" else "Basic Auth"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully authenticated with Jira using {auth_status}"
                    }
                ]
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Authentication failed. Please ensure OAuth or Basic Auth credentials are configured."
                    }
                ],
                "isError": True
            }

    async def _clear_session(self) -> Dict:
        """Handle clear_session tool call."""
        try:
            self.clear_session()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "OAuth session cleared successfully. Re-authentication will be required for next BRD processing."
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error clearing session: {str(e)}"
                    }
                ],
                "isError": True
            }

    async def _get_all_projects(self) -> Dict:
        """Get all Jira projects."""
        try:
            response = self._make_api_request('GET', '/project/search', params={'maxResults': 50}, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                projects = []
                for p in data.get('values', []):
                    projects.append({
                        "key": p.get("key"),
                        "name": p.get("name"),
                        "id": p.get("id")
                    })
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(projects)} Jira projects:\n" + 
                                   "\n".join([f"- {p['name']} ({p['key']})" for p in projects])
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to get projects: {response.status_code} {response.text}"
                        }
                    ],
                    "isError": True
                }
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            return {
                "content": [{"type": "text", "text": f"Error getting projects: {str(e)}"}],
                "isError": True
            }
    
    async def _create_project(self, arguments: Dict) -> Dict:
        """Create a new Jira project with enhanced error handling and detailed logging."""
        project_key = arguments.get('projectKey')
        project_name = arguments.get('projectName')
        project_type = arguments.get('projectType', 'software')
        
        if not project_key or not project_name:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Both projectKey and projectName are required"
                    }
                ],
                "isError": True
            }
        
        try:
            # First, get current user to use as project lead
            
            logger.debug(f"Getting current user for project lead...")
            user_response = self._make_api_request('GET', '/myself')
            current_user = None
            if user_response.status_code == 200:
                user_data = user_response.json()
                current_user = user_data.get('accountId')
                logger.debug(f"Current user accountId: {current_user}")


            # Create simplified payload that works with Jira Cloud API
            payload = {
                "key": project_key,
                "name": project_name,
                "projectTypeKey": project_type,
                "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-scrum-template",
                "description": f"Project {project_key} created via MCP Agent486",
                "assigneeType": "PROJECT_LEAD"
            }            # Add project lead if we have current user
            if current_user:
                payload["leadAccountId"] = current_user
            
            logger.debug(f"Creating Jira project with payload: {payload}")
            
            # Log request details for debugging
            base_url = self._get_base_url()
            headers = self._get_auth_headers()
            logger.debug(f"API URL: {base_url}/rest/api/3/project")
            logger.debug(f"Headers: {headers}")
            
            response = self._make_api_request('POST', '/project', json=payload, timeout=30)
            logger.debug(f"Jira project creation response: status={response.status_code}, body={response.text}")
            
            if response.status_code == 201:
                project_data = response.json()
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"✅ Project '{project_name}' creation initiated successfully!\nProject Key: {project_key}\nProject ID: {project_data.get('id', 'N/A')}"
                        }
                    ]
                }
            elif response.status_code in [401, 403]:
                # Enhanced 401 error handling with exact ADO-style messaging
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f"\nDetails: {error_data.get('message', 'Unauthorized; scope does not match')}"
                except:
                    error_detail = f"\nDetails: Unauthorized; scope does not match"
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Project creation failed: Insufficient permissions{error_detail}\n\n" +
                                   f"🔧 **Solution Options:**\n" +
                                   f"1. Ask your Jira administrator to grant 'Administer Projects' permission\n" +
                                   f"2. Ask admin to grant 'Create Projects' global permission\n" +
                                   f"3. Manually create project '{project_name}' with key '{project_key}' in Jira\n" +
                                   f"4. Use an existing project instead\n" +
                                   f"5. Switch to ADO platform if Jira permissions cannot be granted\n\n" +
                                   f"**Current OAuth Scope**: Ensure your OAuth app has 'write:project:jira' scope"
                        }
                    ],
                    "isError": True
                }
            elif response.status_code == 400:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('message', response.text)
                field_errors = error_data.get('errors', {})
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Project creation failed: {error_msg}\n\n" +
                                   f"🔧 **Solution Options:**\n" +
                                   f"1. Project key '{project_key}' may already exist - try a different key\n" +
                                   f"2. Project name '{project_name}' may be invalid or duplicate\n" +
                                   f"3. Check project key format (must be uppercase, no spaces, 2-10 chars)\n" +
                                   f"4. Manually create project in Jira with different settings\n\n" +
                                   f"**Field Errors**: {field_errors if field_errors else 'None'}"
                        }
                    ],
                    "isError": True
                }
            elif response.status_code == 403:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Project creation forbidden: Access denied\n\n" +
                                   f"🔧 **Solution Options:**\n" +
                                   f"1. Contact Jira administrator for project creation permissions\n" +
                                   f"2. Request to be added to 'jira-administrators' group\n" +
                                   f"3. Use an existing project instead\n" +
                                   f"4. Switch to ADO platform\n\n" +
                                   f"**Error Details**: {response.text}"
                        }
                    ],
                    "isError": True
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Project creation failed: HTTP {response.status_code}\n\n" +
                                   f"🔧 **Solution Options:**\n" +
                                   f"1. Check Jira instance connectivity and configuration\n" +
                                   f"2. Verify user account permissions\n" +
                                   f"3. Try again after a few minutes (temporary server issue)\n" +
                                   f"4. Manually create project '{project_name}' with key '{project_key}'\n" +
                                   f"5. Contact Jira administrator for assistance\n\n" +
                                   f"**Error Details**: {response.text}"
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return {
                "content": [
                    {
                        "type": "text", 
                        "text": f" Project creation error: {str(e)}\n\n" +
                               f"🔧 **Solution Options:**\n" +
                               f"1. Check network connectivity to Jira instance\n" +
                               f"2. Verify Jira instance URL and authentication\n" +
                               f"3. Try again after checking connection\n" +
                               f"4. Manually create project '{project_name}' with key '{project_key}'\n" +
                               f"5. Switch to ADO platform if Jira issues persist"
                    }
                ],
                "isError": True
            }
    
    async def _create_issue(self, arguments: Dict) -> Dict:
        """Create a new issue with enhanced parent_id support and validation."""
        project = arguments.get('project')
        title = arguments.get('title')
        description = arguments.get('description', '')
        issue_type = arguments.get('issueType', 'Task')
        parent_id = arguments.get('parent_id')
        priority = arguments.get('priority')
        labels = arguments.get('labels', [])
        
        if not project or not title:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Both project and title are required"
                    }
                ],
                "isError": True
            }
        
        # Critical validation for Sub-task creation
        if issue_type.lower() == 'sub-task' and not parent_id:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Sub-task creation failed: parent_id is required for Sub-task creation.\n\n" +
                               f"🔧 **Solution**: Create parent Task first, then Sub-task with parent_id.\n" +
                               f"**Prevention**: Always create parents before children in hierarchical workflows."
                    }
                ],
                "isError": True
            }
        
        try:
            payload = {
                "fields": {
                    "project": {"key": project},
                    "summary": title,
                    "issuetype": {"name": issue_type}
                }
            }
            
            # Add description if provided
            if description:
                payload["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                }
            
            # Add parent relationship if provided (works for Sub-tasks and Stories under Epics)
            if parent_id:
                payload["fields"]["parent"] = {"key": parent_id}
                logger.debug(f"Creating {issue_type} with parent_id: {parent_id}")
            
            # Add priority if provided
            if priority:
                payload["fields"]["priority"] = {"name": priority}
            
            # Add labels if provided
            if labels:
                if isinstance(labels, str):
                    labels = [labels]
                payload["fields"]["labels"] = labels
            
            logger.debug(f"Creating issue with payload: {payload}")
            response = self._make_api_request('POST', '/issue', json=payload, timeout=15)
            logger.debug(f"Create issue response: status={response.status_code}, body={response.text}")
            
            if response.status_code == 201:
                issue = response.json()
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"✅ Created {issue_type} {issue['key']}: {title}"
                        }
                    ]
                }
            elif response.status_code == 400:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('errorMessages', [])
                field_errors = error_data.get('errors', {})
                
                # Handle specific Sub-task parent issue error
                if 'parent' in field_errors:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"❌ Sub-task creation failed: Invalid parent issue '{parent_id}'\n\n" +
                                       f"🔧 **Solution**: Verify parent issue exists and is accessible.\n" +
                                       f"**Error Details**: {field_errors.get('parent', 'Unknown parent error')}"
                            }
                        ],
                        "isError": True
                    }
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to create issue: {response.status_code}\nErrors: {error_msg}\nField errors: {field_errors}"
                        }
                    ],
                    "isError": True
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to create issue: {response.status_code} {response.text}"
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return {
                "content": [{"type": "text", "text": f"Error creating issue: {str(e)}"}],
                "isError": True
            }
    
    async def _get_issue_types(self, arguments: Dict) -> Dict:
        """Get issue types for a project."""
        project = arguments.get('project')
        
        if not project:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Project parameter is required"
                    }
                ],
                "isError": True
            }
        
        try:
            params = {"projectKeys": project, "expand": "projects.issuetypes"}
            response = self._make_api_request('GET', '/issue/createmeta', params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                issue_types = []
                
                for proj in data.get("projects", []):
                    if proj.get("key") == project:
                        for issue_type in proj.get("issuetypes", []):
                            issue_types.append(issue_type["name"])
                        break
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Available issue types for {project}:\n" +
                            "\n".join([f"- {t}" for t in issue_types])
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to get issue types: {response.status_code} {response.text}"
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Error getting issue types: {e}")
            return {
                "content": [{"type": "text", "text": f"Error getting issue types: {str(e)}"}],
                "isError": True
            }
    
    async def _search_issues(self, arguments: Dict) -> Dict:
        """Search for issues."""
        project = arguments.get('project')
        jql = arguments.get('jql', f'project = "{project}"')
        
        if not project:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Project parameter is required"
                    }
                ],
                "isError": True
            }
        
        try:
            payload = {
                "jql": jql,
                "maxResults": 10,
                "fields": ["key", "summary", "status"]
            }
            
            response = self._make_api_request('POST', '/search/jql', json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                issues = data.get("issues", [])
                
                if issues:
                    issues_text = "\n".join([
                        f"- {issue['key']}: {issue['fields']['summary']}"
                        for issue in issues
                    ])
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Found {len(issues)} issues:\n{issues_text}"
                            }
                        ]
                    }
                else:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "No issues found"
                            }
                        ]
                    }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to search issues: {response.status_code} {response.text}"
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            return {
                "content": [{"type": "text", "text": f"Error searching issues: {str(e)}"}],
                "isError": True
            }
    
    async def _get_issue(self, arguments: Dict) -> Dict:
        """Get a specific issue."""
        issue_key = arguments.get('issueKey')
        
        if not issue_key:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Issue key parameter is required"
                    }
                ],
                "isError": True
            }
        
        try:
            response = self._make_api_request('GET', f'/issue/{issue_key}', timeout=15)
            
            if response.status_code == 200:
                issue = response.json()
                fields = issue.get("fields", {})
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Issue {issue_key}:\n" +
                                   f"Summary: {fields.get('summary', 'N/A')}\n" +
                                   f"Status: {fields.get('status', {}).get('name', 'N/A')}\n" +
                                   f"Type: {fields.get('issuetype', {}).get('name', 'N/A')}"
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to get issue: {response.status_code} {response.text}"
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Error getting issue: {e}")
            return {
                "content": [{"type": "text", "text": f"Error getting issue: {str(e)}"}],
                "isError": True
            }

    async def _update_issue(self, arguments: Dict) -> Dict:
        """Update an existing issue."""
        issue_key = arguments.get('issueKey')
        fields = arguments.get('fields', {})
        
        if not issue_key:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Issue key parameter is required"
                    }
                ],
                "isError": True
            }
        
        if not fields:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Fields parameter is required for update"
                    }
                ],
                "isError": True
            }
        
        try:
            # Convert parent_id to proper Jira parent format
            if 'parent_id' in fields:
                parent_id = fields.pop('parent_id')  # Remove parent_id
                if parent_id:
                    fields['parent'] = {'key': parent_id}  # Add proper parent format
            
            payload = {"fields": fields}
            
            response = self._make_api_request('PUT', f'/issue/{issue_key}', json=payload, timeout=15)
            
            if response.status_code == 204:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"✅ Successfully updated issue {issue_key}"
                        }
                    ]
                }
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get('errorMessages', [response.text])
                except:
                    pass
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to update issue: {response.status_code} {error_msg}"
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Error updating issue: {e}")
            return {
                "content": [{"type": "text", "text": f"Error updating issue: {str(e)}"}],
                "isError": True
            }

async def handle_request(request_line: str, server: JiraMCPServer) -> Optional[Dict]:
    """Handle a single MCP request."""
    request_data = None
    try:
        request_data = json.loads(request_line.strip())
        logger.debug(f"Received request: {request_data}")
        
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        if method == "initialize":
            result = await server.handle_initialize(params)
        elif method == "notifications/initialized":
            # Handle initialization notification (no response required)
            logger.debug("Received initialization notification")
            return None
        elif method == "tools/list":
            result = await server.handle_tools_list(params)
        elif method == "tools/call":
            result = await server.handle_tools_call(params)
        else:
            result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}
        
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        
        logger.debug(f"Sending response: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        request_id = request_data.get("id") if request_data else None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
        }

async def main():
    """Main server loop."""
    server = JiraMCPServer()
    logger.info("Jira MCP Server started")
    
    try:
        while True:
            # Read from stdin
            line = sys.stdin.readline()
            if not line:
                break
                
            response = await handle_request(line, server)
            if response:
                # Write to stdout
                print(json.dumps(response), flush=True)
                
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())