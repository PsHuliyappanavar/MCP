#!/usr/bin/env python3
"""
ADO MCP Server implementing the Model Context Protocol for AI Toolkit integration.
This server communicates via JSON-RPC over stdin/stdout as required by AI Toolkit.
"""

import asyncio
import json
import sys
import os
import logging
import requests
import base64
import urllib.parse
import threading
import time
import webbrowser
from typing import Dict, List, Any, Optional
from requests.auth import HTTPBasicAuth
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
    to prevent rate-limit issues with ADO API.
    """
    func_name = getattr(tool_func, '__name__', str(tool_func))
    logger.info(f"Waiting 2 seconds before calling {func_name}")
    time.sleep(2)
    logger.info(f"Executing {func_name}")
    return tool_func(*args, **kwargs)

async def async_safe_call(tool_func, *args, **kwargs):
    """
    Async helper function that adds a 2-second wait before executing async tool functions
    to prevent rate-limit issues with ADO API.
    """
    func_name = getattr(tool_func, '__name__', str(tool_func))
    logger.info(f"Waiting 2 seconds before calling {func_name}")
    time.sleep(2)  # Using time.sleep instead of asyncio.sleep to ensure blocking
    logger.info(f"Executing {func_name}")
    return await tool_func(*args, **kwargs)

class ADOOAuthTokenManager:
    """Manages OAuth 2.0 tokens for ADO authentication using Azure AD."""

    def __init__(self, client_id: str, client_secret: str, tenant_id: str, redirect_uri: str = "http://localhost:9001/oauth/callback"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.redirect_uri = redirect_uri
        self.auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.ado_url = None  # Will be set after organization selection
        self.organizations = None  # List of available organizations
        self.selected_organization = None  # Currently selected organization

        # OAuth flow management
        self.oauth_app = None
        self.oauth_thread = None
        self.auth_complete = threading.Event()

        # DO NOT load existing tokens - force fresh authentication each session

    def start_oauth_flow(self) -> str:
        """Start the OAuth flow and return the authorization URL."""
        # Start Flask app for OAuth callback
        self._start_oauth_server()

        # Build authorization URL with ADO-specific scopes
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': 'https://app.vssps.visualstudio.com/user_impersonation offline_access',
            'response_mode': 'query'
        }

        auth_url = f"{self.auth_url}?{urlencode(params)}"

        logger.info(f"Opening browser for ADO OAuth authorization: {auth_url}")


        try:
            webbrowser.open(auth_url) # Automatically operns web browser
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
                try:
                    success = self._exchange_code_for_tokens(code)
                    if success:
                        logger.info("Token exchange completed successfully")
                        self.auth_complete.set()
                        return "OAuth successful! You can close this window."
                    else:
                        logger.error("Token exchange failed")
                        self.auth_complete.set()
                        return "OAuth failed during token exchange. Please check the logs."
                except Exception as e:
                    logger.error(f"Exception during token exchange: {e}")
                    self.auth_complete.set()
                    return f"OAuth failed with error: {str(e)}"

            return "Invalid callback"

        def run_server():
            if self.oauth_app:
                self.oauth_app.run(host='localhost', port=9001, debug=False, use_reloader=False)

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
                'redirect_uri': self.redirect_uri,
                'scope': 'https://app.vssps.visualstudio.com/user_impersonation offline_access'
            }

            response = requests.post(self.token_url, data=payload, timeout=30)

            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens.get('access_token')
                self.refresh_token = tokens.get('refresh_token')
                expires_in = tokens.get('expires_in', 3600)
                self.expires_at = time.time() + expires_in - 300  # Refresh 5 minutes early

                # Clear any cached organization data to force fresh fetch
                self.organizations = None
                self.selected_organization = None
                self.ado_url = None

                logger.info("ADO OAuth tokens obtained successfully")
                logger.info(f"Access token length: {len(self.access_token) if self.access_token else 0}")

                # First return success, then try to get organization URL
                logger.info("Token exchange successful, returning success immediately")

                # Get ADO organization URL dynamically in background (non-blocking)
                try:
                    logger.info("Fetching ADO organization...")
                    # Get organizations after token exchange
                    if self._get_ado_organizations():
                        org_success = True
                        logger.info("Organization list fetched successfully")
                    else:
                        org_success = False
                        logger.error("Failed to fetch organization list")

                    if org_success:
                        logger.info("ADO organizations available for selection")
                    else:
                        logger.warning("Failed to fetch ADO organizations, will try again later")
                except Exception as e:
                    logger.warning(f"Organization fetch failed: {e}, will try again later")

                return True
            else:
                logger.error(f"Token exchange failed: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return False

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API calls."""
        if not self.access_token:
            raise Exception("No access token available")

        return {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }

    def _get_ado_organizations(self) -> bool:
        """
        Fetch all Azure DevOps organizations accessible to the authenticated user.
        Returns True if successful, False otherwise.
        """
        if not self.access_token:
            logger.error("No access token found. Please authenticate first.")
            return False

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        }

        try:
            # Step 1️: Get the authenticated user's profile to retrieve their memberId
            profile_url = "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.0"
            logger.info("Step 1: Fetching user profile to get memberId...")
            profile_resp = requests.get(profile_url, headers=headers, timeout=15)

            if profile_resp.status_code != 200:
                logger.error(f"Failed to get user profile: {profile_resp.status_code} {profile_resp.text}")
                return False

            profile_data = profile_resp.json()
            member_id = profile_data.get("id")
            if not member_id:
                logger.error("Could not extract memberId from profile response.")
                logger.debug(f"Profile response keys: {list(profile_data.keys())}")
                return False

            logger.info(f" Retrieved memberId: {member_id}")

            # Step 2️: Get all accounts (organizations) for the user
            accounts_url = f"https://app.vssps.visualstudio.com/_apis/accounts?memberId={member_id}&api-version=7.0"
            logger.info("Step 2: Fetching organizations using memberId...")
            accounts_resp = requests.get(accounts_url, headers=headers, timeout=15)
            if accounts_resp.status_code != 200:
                logger.error(f"Failed to fetch ADO organizations: {accounts_resp.status_code} {accounts_resp.text}")
                return False

            accounts_data = accounts_resp.json()
            orgs = accounts_data.get("value", [])

            if not orgs:
                logger.warning(
                    "No organizations found in ADO response. "
                    "Ensure your OAuth scopes include 'vso.profile', 'vso.account', or 'user_impersonation'."
                )
                self.organizations = []
                return False

            # Step 3️: Process and cache results
            self.organizations = []
            for org in orgs:
                # Normalize organization data structure
                org_info = {
                    'accountId': org.get('accountId') or org.get('id'),
                    'accountName': org.get('accountName') or org.get('name'),
                    'accountUri': org.get('accountUri') or f"https://dev.azure.com/{org.get('accountName') or org.get('name')}",
                    'properties': org.get('properties', {})
                }
                if org_info['accountName']:  # Only add if we have a name
                    self.organizations.append(org_info)

            logger.info(f" Found {len(self.organizations)} ADO organization(s):")
            for org in self.organizations:
                logger.info(f"  - {org['accountName']} (ID: {org['accountId']})")

            # Optionally set the first org as default URL (for legacy compatibility)
            if self.organizations:
                first_org = self.organizations[0]
                org_name = first_org.get("accountName")
                # Don't auto-set ado_url here - let user select explicitly
                logger.info(f"First organization: {org_name}")

            return True

        except Exception as e:
            logger.error(f"Exception in _get_ado_organizations: {e}")
            return False

    def select_organization(self, org_name: str):
        """Select an organization to work with."""
        # First try to validate the organization exists by checking if we can access it
        if self._validate_organization_access(org_name):
            # If we can access it, add it to our list and select it
            org_info = {
                'accountId': None,  # We don't need the ID for basic operations
                'accountName': org_name,
                'accountUri': f"https://dev.azure.com/{org_name}",
                'properties': {}
            }

            if not self.organizations:
                self.organizations = []

            # Check if already in list
            existing = next((org for org in self.organizations if org['accountName'] == org_name), None)
            if not existing:
                self.organizations.append(org_info)

            self.selected_organization = org_info
            self.ado_url = f"https://dev.azure.com/{org_name}"
            logger.info(f"Selected organization: {org_name}")
            logger.info(f"ADO URL set to: {self.ado_url}")
            return True

        # Fallback to original logic for discovered organizations
        if not self.organizations:
            logger.error("No organizations available to select from")
            return False

        for org in self.organizations:
            if org['accountName'] == org_name:
                self.selected_organization = org
                self.ado_url = f"https://dev.azure.com/{org_name}"
                logger.info(f"Selected organization: {org_name}")
                logger.info(f"ADO URL set to: {self.ado_url}")
                return True

        logger.error(f"Organization '{org_name}' not found in available organizations")
        return False

    def _validate_organization_access(self, org_name: str):
        """Validate if the user has access to the specified organization."""
        try:
            if not self.access_token:
                return False

            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }

            # Try to access the organization's projects endpoint
            test_url = f"https://dev.azure.com/{org_name}/_apis/projects?api-version=7.1-preview.4"
            response = requests.get(test_url, headers=headers, timeout=10)

            if response.status_code == 200:
                logger.info(f"Confirmed access to organization: {org_name}")
                return True
            elif response.status_code == 404:
                logger.warning(f"Organization '{org_name}' not found or not accessible")
                return False
            elif response.status_code == 401 or response.status_code == 403:
                logger.warning(f"Access denied to organization '{org_name}' - user may not be a member")
                return False
            else:
                logger.warning(f"Unexpected response {response.status_code} when validating organization '{org_name}'")
                return False

        except Exception as e:
            logger.error(f"Error validating organization access: {e}")
            return False

    def _create_ado_organization(self, org_name: str, region: str = "Central US"):
        """Create a new ADO organization."""
        try:
            if not self.access_token:
                logger.error("No access token available for organization creation")
                return False

            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            # Organization creation payload
            payload = {
                "accountName": org_name,
                "region": region,
                "properties": {
                    "Microsoft.VisualStudio.Services.Account.AccountCreationSource": "Manual"
                }
            }

            # Create organization via Azure DevOps Services REST API
            response = requests.post(
                'https://app.vssps.visualstudio.com/_apis/accounts',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200 or response.status_code == 201:
                org_data = response.json()
                logger.info(f"Organization '{org_name}' created successfully")

                # Add to organizations list and select it
                new_org = {
                    'accountId': org_data.get('accountId'),
                    'accountName': org_name,
                    'accountUri': org_data.get('accountUri'),
                    'properties': org_data.get('properties', {})
                }

                if not self.organizations:
                    self.organizations = []
                self.organizations.append(new_org)

                # Auto-select the newly created organization
                self.select_organization(org_name)
                return True
            else:
                logger.error(f"Failed to create organization: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating ADO organization: {e}")
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
                'refresh_token': self.refresh_token,
                'scope': 'https://app.vssps.visualstudio.com/user_impersonation offline_access'
            }

            response = requests.post(self.token_url, data=payload, timeout=30)

            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens.get('access_token')

                # Update refresh token if provided
                if 'refresh_token' in tokens:
                    self.refresh_token = tokens['refresh_token']

                expires_in = tokens.get('expires_in', 3600)
                self.expires_at = time.time() + expires_in - 300

                # DO NOT save refreshed tokens for session-based authentication

                logger.info("ADO access token refreshed successfully")
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
        has_token = bool(self.access_token)
        has_orgs = bool(self.organizations is not None)
        logger.debug(f"Authentication check - Has token: {has_token}, Has orgs: {has_orgs}")

        # We're authenticated if we have a token - organizations can be fetched later
        return bool(self.access_token)

    def _clear_tokens(self):
        """Clear all session tokens."""
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.ado_url = None
        self.organizations = None
        self.selected_organization = None

class ADOMCPServer:
    """ADO MCP Server implementing Model Context Protocol with OAuth"""

    def __init__(self):
        # OAuth-only authentication
        self.oauth_manager = None
        self.auth_method = None
        self.session_authenticated = False  # Track session authentication status

        # OAuth credentials (required)
        client_id = os.getenv("ADO_CLIENT_ID")
        client_secret = os.getenv("ADO_CLIENT_SECRET")
        tenant_id = os.getenv("ADO_TENANT_ID")

        if client_id and client_secret and tenant_id:
            # Initialize OAuth
            self.oauth_manager = ADOOAuthTokenManager(client_id, client_secret, tenant_id)
            logger.info("OAuth credentials configured, OAuth authentication available")

        if not (client_id and client_secret and tenant_id):
            logger.error("OAuth credentials (ADO_CLIENT_ID/SECRET/TENANT_ID) are required")
            sys.exit(1)

        logger.info("Initialized ADO MCP Server with OAuth support (organization URL will be fetched dynamically)")

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
        """Get the base URL for ADO API calls."""
        if self.oauth_manager and self.oauth_manager.access_token:
            # Return the selected organization URL
            return self.oauth_manager.ado_url

        return None

    def _get_auth(self):
        """Get auth method for requests."""
        if self.oauth_manager and self.oauth_manager.is_authenticated():
            return None  # Headers handle OAuth handles validation

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
            if self.oauth_manager.wait_for_authorization(timeout=120):  # 2 minutes timeout
                if self.oauth_manager.is_authenticated():
                    self.auth_method = "oauth"
                    self.session_authenticated = True  # Mark session as authenticated
                    logger.info("OAuth authentication successful - session established")
                    logger.info(f"Organizations fetched: {len(self.oauth_manager.organizations) if self.oauth_manager.organizations else 0}")
                    logger.info(f"Access token present: {bool(self.oauth_manager.access_token)}")
                    return True
                else:
                    logger.error("OAuth authentication failed - not authenticated")
                    logger.error(f"Access token present: {bool(self.oauth_manager.access_token if self.oauth_manager else False)}")
                    logger.error(f"ADO URL present: {bool(self.oauth_manager.ado_url if self.oauth_manager else False)}")
            else:
                logger.error("OAuth authentication timed out")

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

        logger.info("OAuth session cleared successfully")

    async def handle_initialize(self, params: Dict) -> Dict:
        """Handle MCP initialize request. metadata about the server."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "ado-mcp-server",
                "version": "1.0.0"
            }
        }

    async def handle_tools_list(self, params: Dict) -> Dict:
        """Handle tools/list request with context-aware descriptions."""
        return {
            "tools": [
                {
                    "name": "authenticate",
                    "description": "Authenticate with ADO using OAuth 2.0 - REQUIRED FIRST",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "get_organizations",
                    "description": "Get all available ADO organizations and prompt user for selection - REQUIRED after authentication",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "select_organization",
                    "description": "Select an organization based on user choice - REQUIRED after get_organizations",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "organizationName": {"type": "string"}
                        },
                        "required": ["organizationName"]
                    }
                },
                {
                    "name": "create_organization",
                    "description": "Create a new ADO organization when requested by user or none exist",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "organizationName": {"type": "string"},
                            "region": {"type": "string", "default": "Central US"}
                        },
                        "required": ["organizationName"]
                    }
                },
                {
                    "name": "get_all_projects",
                    "description": "Get all ADO projects from selected organization - Use ONLY for project discovery and conflict checking",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "create_project", 
                    "description": "Create a new ADO project - Use ONLY when new project needed",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "projectKey": {"type": "string"},
                            "projectName": {"type": "string"},
                            "projectType": {"type": "string", "default": "Agile"}
                        },
                        "required": ["projectKey", "projectName"]
                    }
                },
                {
                    "name": "get_issue_types",
                    "description": "Get available work item types - Use ONCE per project for hierarchy planning",
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
                    "description": "Create work items with hierarchy - PRIMARY creation tool",
                    "inputSchema": {
                        "type": "object", 
                        "properties": {
                            "project": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "issueType": {"type": "string", "default": "User Story"},
                            "parent_id": {"type": "string"},
                            "priority": {"type": "string"},
                            "labels": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["project", "title"]
                    }
                },
                {
                    "name": "get_issue",
                    "description": "Get specific work item details - Use ONLY for verification after creation errors",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "issueId": {"type": "string"}
                        },
                        "required": ["issueId"]
                    }
                },
                {
                    "name": "search_issues", 
                    "description": "Search for existing work items - Use ONLY if user requests finding existing items",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string"},
                            "query": {"type": "string"}
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
            elif tool_name == "get_organizations":
                return await async_safe_call(self._get_organizations)
            elif tool_name == "select_organization":
                return await async_safe_call(self._select_organization, arguments)
            elif tool_name == "create_organization":
                return await async_safe_call(self._create_organization, arguments)
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

    async def _authenticate(self) -> Dict:
        """Handle authentication tool call - always force fresh OAuth."""
        # Force fresh OAuth authentication for each session
        if await self._authenticate_if_needed():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f" Successfully authenticated with ADO using OAuth 2.0"
                    }
                ]
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": " Authentication failed. Please ensure OAuth credentials are configured."
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
                        "text": " OAuth session cleared successfully. Re-authentication will be required for next BRD processing."
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

    async def _get_organizations(self) -> Dict:
        """Get all available ADO organizations."""
        # Check if session is authenticated
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Not authenticated. Please authenticate first."}],
                "isError": True
            }

        try:
            # If organizations are already cached (e.g., from mocking), use them directly
            if self.oauth_manager.organizations is not None:
                orgs = self.oauth_manager.organizations
                if not orgs:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "No organizations found via auto-discovery.\n\n" +
                                    "This could happen if:\n" +
                                    "• You don't have any Azure DevOps organizations\n" +
                                    "• Your organizations are in a different tenant\n" +
                                    "• The OAuth token needs additional permissions\n\n" +
                                    "**USER ACTION REQUIRED:**\n" +
                                    "Please choose one of the following options:\n" +
                                    "1. **Create a new organization**: Use create_organization tool with your desired organization name\n" +
                                    "2. **Try direct access**: Use select_organization tool with your known organization name\n" +
                                    "3. **Contact admin**: Ask an admin to invite you to an existing organization\n\n" +
                                    "Example: If you want to create 'MyCompany' organization, use:\n" +
                                    "create_organization with organizationName='MyCompany'"
                            }
                        ]
                    }

                if len(orgs) > 0:
                    org_list = "\n".join([f"  {i+1}. {org['accountName']} (ID: {org.get('accountId', 'Unknown')})" for i, org in enumerate(orgs)])
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f" Found {len(orgs)} ADO organization(s):\n{org_list}\n\n" +
                                    f"**USER ACTION REQUIRED:**\n" +
                                    f"Please select an organization using select_organization tool.\n\n" +
                                    f"Use the exact organization name from the list above.\n" +
                                    f"Example: select_organization with organizationName='<organization_name>'\n\n" +
                                    f"Or to create a new organization, use:\n" +
                                    f"create_organization with organizationName='YourNewOrgName'"
                            }
                        ]
                    }

            # Fetch organizations from API
            if self.oauth_manager._get_ado_organizations():
                orgs = self.oauth_manager.organizations or []
                if not orgs:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": " No organizations found via auto-discovery.\n\n" +
                                    "This could happen if:\n" +
                                    "• You don't have any Azure DevOps organizations\n" +
                                    "• Your organizations are in a different tenant\n" +
                                    "• The OAuth token needs additional permissions\n\n" +
                                    "**USER ACTION REQUIRED:**\n" +
                                    "Please choose one of the following options:\n" +
                                    "1. **Create a new organization**: Use create_organization tool with your desired organization name\n" +
                                    "2. **Try direct access**: Use select_organization tool with your known organization name\n" +
                                    "3. **Contact admin**: Ask an admin to invite you to an existing organization\n\n" +
                                    "Example: If you want to create 'MyCompany' organization, use:\n" +
                                    "create_organization with organizationName='MyCompany'"
                            }
                        ]
                    }

                org_list = "\n".join([f"  {i+1}. {org['accountName']} (ID: {org.get('accountId', 'Unknown')})" for i, org in enumerate(orgs)])
                return {

                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(orgs)} ADO organization(s):\n{org_list}\n\n" +
                                f"**USER ACTION REQUIRED:**\n" +
                                f"Please select an organization using select_organization tool.\n\n" +
                                f"Use the exact organization name from the list above.\n" +
                                f"Example: select_organization with organizationName='<organization_name>'\n\n" +
                                f"Or to create a new organization, use:\n" +
                                f"create_organization with organizationName='YourNewOrgName'"
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text", 
                            "text": "Could not retrieve organizations via API.\n\n" +
                                "**USER ACTION REQUIRED:**\n" +
                                "If you know your organization name, try:\n" +
                                "• select_organization with organizationName='YourOrgName'\n" +
                                "• create_organization with organizationName='YourNewOrgName'"
                        }
                    ]
                }

        except Exception as e:
            logger.error(f"Error getting organizations: {e}")
            return {
                "content": [{"type": "text", "text": f" Error: {str(e)}"}],
                "isError": True
            }

    async def _select_organization(self, arguments: Dict) -> Dict:
        """Select an organization to work with."""
        # Check if session is authenticated
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": " Not authenticated. Please authenticate first."}],
                "isError": True
            }

        org_name = arguments.get('organizationName')
        if not org_name:
            return {
                "content": [{"type": "text", "text": " Organization name is required"}],
                "isError": True
            }

        try:
            if self.oauth_manager.select_organization(org_name):
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Selected organization: {org_name}\nURL: {self.oauth_manager.ado_url}\n\nNext: You can now use get_all_projects to see available projects."
                        }
                    ]
                }
            else:
                # List available organizations for user and offer to create new one
                orgs = self.oauth_manager.organizations if self.oauth_manager.organizations else []
                org_list = "\n".join([f"  - {org['accountName']}" for org in orgs]) if orgs else "  - No organizations available"

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Organization '{org_name}' not found.\n\n" +
                                f"Available organizations:\n{org_list}\n\n" +
                                f"**USER ACTION REQUIRED:**\n" +
                                f"Choose one of the following options:\n" +
                                f"1. **Select an existing organization**: Use select_organization with one of the available organization names above\n" +
                                f"2. **Create new organization '{org_name}'**: Use create_organization with organizationName='{org_name}'\n" +
                                f"3. **Create organization with different name**: Use create_organization with your preferred organizationName\n\n" +
                                f"Example to create '{org_name}':\n" +
                                f"create_organization with organizationName='{org_name}'"
                        }
                    ],
                    "isError": True
                }

        except Exception as e:
            logger.error(f"Error selecting organization: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }

    async def _create_organization(self, arguments: Dict) -> Dict:
        """Create a new ADO organization."""
        # Check if session is authenticated
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Not authenticated. Please authenticate first."}],
                "isError": True
            }

        org_name = arguments.get('organizationName')
        region = arguments.get('region', 'Central US')

        if not org_name:
            return {
                "content": [{"type": "text", "text": "Organization name is required"}],
                "isError": True
            }

        try:
            if self.oauth_manager._create_ado_organization(org_name, region):
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Organization '{org_name}' created successfully in {region}!\nURL: {self.oauth_manager.ado_url}\n\nThe organization is now selected and ready for use. Next: Use get_all_projects to see available projects."
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Failed to create organization '{org_name}'. This may be due to:\n- Name already exists\n- Insufficient permissions\n- Network issues\n\nPlease try a different name or check your permissions."
                        }
                    ],
                    "isError": True
                }

        except Exception as e:
            logger.error(f"Error creating organization: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }

    def _make_api_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated API request to ADO."""
        headers = self._get_auth_headers()
        base_url = self._get_base_url()
        auth = self._get_auth()

        if not base_url:
            raise Exception("No valid ADO URL configured")

        url = f"{base_url}{endpoint}"

        # Set up request parameters
        request_kwargs = kwargs.copy()

        # Merge custom headers with auth headers
        if headers:
            # OAuth - use headers
            if 'headers' in request_kwargs:
                # Merge custom headers with auth headers
                merged_headers = headers.copy()
                merged_headers.update(request_kwargs['headers'])
                request_kwargs['headers'] = merged_headers
            else:
                request_kwargs['headers'] = headers
        elif auth:
            # This should not happen in OAuth-only mode
            request_kwargs['auth'] = auth
        else:
            raise Exception("No valid authentication method available")

        # Make the request
        return requests.request(method, url, **request_kwargs)

    async def _get_all_projects(self) -> Dict:
        """Get all ADO projects."""
        # Check if session is authenticated (only need access token, not URL yet)
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Authentication required. Please call 'authenticate' first."}],
                "isError": True
            }

        # Check if organization is selected
        if not self.oauth_manager.ado_url:
            return {
                "content": [{"type": "text", "text": "No organization selected. Please use select_organization first."}],
                "isError": True
            }

        try:
            response = self._make_api_request('GET', '/_apis/projects?api-version=7.1', timeout=15)

            if response.status_code == 200:
                data = response.json()
                projects = []
                for p in data.get("value", []):
                    projects.append({
                        "key": p.get("name"),  # ADO uses name as key
                        "name": p.get("name"),
                        "id": p.get("id")
                    })

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(projects)} ADO projects:\n" + 
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
        """Create a new ADO project."""
        # Check if session is authenticated (only need access token, not URL yet)
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Authentication required. Please call 'authenticate' first."}],
                "isError": True
            }

        # Check if organization is selected
        if not self.oauth_manager.ado_url:
            return {
                "content": [{"type": "text", "text": "No organization selected. Please use select_organization first."}],
                "isError": True
            }

        project_key = arguments.get('projectKey', 'PROJ')
        project_name = arguments.get('projectName', 'New Project')

        # First check if project already exists
        try:
            existing_projects_response = self._make_api_request('GET', '/_apis/projects?api-version=7.1', timeout=15)
            if existing_projects_response.status_code == 200:
                existing_projects_data = existing_projects_response.json()
                existing_project_names = [p.get("name") for p in existing_projects_data.get("value", [])]
                
                if project_name in existing_project_names:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"✅ Project '{project_name}' already exists in the organization.\n\n" +
                                    f"💡 You can now proceed to use get_issue_types or create_issue tools with this project.\n\n" +
                                    f"Example: get_issue_types with project='{project_name}'"
                            }
                        ]
                    }
        except Exception as e:
            logger.warning(f"Could not check existing projects: {e}")

        template_id = "6b724908-ef14-45cf-84f8-768b5384da45"

        payload = {
            "name": project_name,
            "description": f"Project {project_key} created via MCP",
            "capabilities": {
                "versioncontrol": {"sourceControlType": "Git"},
                "processTemplate": {"templateTypeId": template_id}
            },
            "visibility": "private"
        }

        response = self._make_api_request('POST', '/_apis/projects?api-version=7.1', json=payload, timeout=30)

        if response.status_code == 202:
            # ADO project creation is asynchronous
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"✅ Project '{project_name}' creation initiated successfully!\n\n" +
                            f"⏳ **Important**: ADO project creation is asynchronous and may take 1-2 minutes to complete.\n\n" +
                            f"💡 **Next Steps**:\n" +
                            f"1. Wait a moment for project creation to complete\n" +
                            f"2. Use get_all_projects to verify the project is ready\n" +
                            f"3. Then use get_issue_types with project='{project_name}' to see available work item types\n\n" +
                            f"📝 **Project Details**:\n" +
                            f"• Name: {project_name}\n" +
                            f"• Key: {project_key}\n" +
                            f"• Template: Agile"
                    }
                ]
            }
        elif response.status_code == 400:
            # Handle specific 400 errors
            try:
                error_data = response.json()
                error_message = error_data.get('message', response.text)
                
                if 'already exists' in error_message.lower():
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"✅ Project '{project_name}' already exists!\n\n" +
                                    f"💡 You can proceed to use this existing project.\n\n" +
                                    f"**Next Steps**:\n" +
                                    f"1. Use get_issue_types with project='{project_name}' to see available work item types\n" +
                                    f"2. Start creating work items with create_issue tool"
                            }
                        ]
                    }
                else:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"❌ Failed to create project '{project_name}':\n\n" +
                                    f"Error: {error_message}\n\n" +
                                    f"💡 **Possible Solutions**:\n" +
                                    f"• Try a different project name\n" +
                                    f"• Check if you have project creation permissions\n" +
                                    f"• Contact your ADO administrator"
                            }
                        ],
                        "isError": True
                    }
            except:
                pass
                
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Failed to create project: {response.status_code} {response.text}"
                    }
                ],
                "isError": True
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Failed to create project: {response.status_code} {response.text}"
                    }
                ],
                "isError": True
            }

    async def _create_issue(self, arguments: Dict) -> Dict:
        """Create a new work item."""
        # Check if session is authenticated (only need access token, not URL yet)
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Authentication required. Please call 'authenticate' first."}],
                "isError": True
            }

        # Check if organization is selected
        if not self.oauth_manager.ado_url:
            return {
                "content": [{"type": "text", "text": "No organization selected. Please use select_organization first."}],
                "isError": True
            }

        project = arguments.get('project')
        title = arguments.get('title')
        description = arguments.get('description', '')
        issue_type = arguments.get('issueType', 'User Story')

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

        encoded_project = urllib.parse.quote(str(project))

        payload = [
            {"op": "add", "path": "/fields/System.Title", "value": title}
        ]
        if description:
            payload.append({"op": "add", "path": "/fields/System.Description", "value": description})

        # Use special content type for ADO work item creation
        headers = {"Content-Type": "application/json-patch+json"}
        response = self._make_api_request('POST', f'/{encoded_project}/_apis/wit/workitems/${issue_type}?api-version=7.1', json=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            work_item = response.json()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"✅ Created {issue_type} #{work_item['id']}: {title}"
                    }
                ]
            }
        elif response.status_code == 404:
            # Handle project not found
            try:
                # Get available projects for better error message
                projects_response = self._make_api_request('GET', '/_apis/projects?api-version=7.1', timeout=15)
                if projects_response.status_code == 200:
                    projects_data = projects_response.json()
                    available_projects = [p.get("name") for p in projects_data.get("value", [])]
                    
                    if available_projects:
                        projects_list = "\n".join([f"  - {p}" for p in available_projects])
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"❌ Cannot create work item: Project '{project}' not found.\n\n" +
                                        f"📋 Available projects:\n{projects_list}\n\n" +
                                        f"💡 **USER ACTION REQUIRED:**\n" +
                                        f"• If project was recently created, wait 1-2 minutes for ADO provisioning\n" +
                                        f"• Use exact project name from the list above\n\n" +
                                        f"Example: create_issue with project='{available_projects[0]}'"
                                }
                            ],
                            "isError": True
                        }
            except Exception as e:
                logger.error(f"Error getting projects for create_issue 404: {e}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Cannot create work item: Project '{project}' not found.\n\n" +
                            f"💡 **Possible Solutions:**\n" +
                            f"• Wait 1-2 minutes if project was recently created\n" +
                            f"• Use get_all_projects to see available project names\n" +
                            f"• Create project using create_project tool"
                    }
                ],
                "isError": True
            }
        else:
            # Handle other errors with better formatting
            try:
                error_data = response.json()
                error_message = error_data.get('message', response.text)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Failed to create {issue_type}: {title}\n\n" +
                                f"Error ({response.status_code}): {error_message}\n\n" +
                                f"💡 **Common Causes:**\n" +
                                f"• Invalid work item type '{issue_type}'\n" +
                                f"• Missing required fields\n" +
                                f"• Project permissions\n\n" +
                                f"**Try:** get_issue_types with project='{project}' to see valid work item types"
                        }
                    ],
                    "isError": True
                }
            except:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Failed to create work item: {response.status_code} {response.text}"
                        }
                    ],
                    "isError": True
                }

    async def _get_issue_types(self, arguments: Dict) -> Dict:
        """Get work item types for a project."""
        # Check if session is authenticated (only need access token, not URL yet)
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Authentication required. Please call 'authenticate' first."}],
                "isError": True
            }

        # Check if organization is selected
        if not self.oauth_manager.ado_url:
            return {
                "content": [{"type": "text", "text": "No organization selected. Please use select_organization first."}],
                "isError": True
            }

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

        # First, validate that the project exists by checking available projects
        try:
            projects_response = self._make_api_request('GET', '/_apis/projects?api-version=7.1', timeout=15)
            
            if projects_response.status_code == 200:
                projects_data = projects_response.json()
                available_projects = [p.get("name") for p in projects_data.get("value", [])]
                
                # Check if the requested project exists (exact match)
                if project not in available_projects:
                    # Try case-insensitive search
                    project_lower = project.lower()
                    matching_projects = [p for p in available_projects if p.lower() == project_lower]
                    
                    if matching_projects:
                        # Found case-insensitive match
                        actual_project_name = matching_projects[0]
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"🔄 Project name case mismatch detected.\n\n" +
                                        f"Requested: '{project}'\n" +
                                        f"Found: '{actual_project_name}'\n\n" +
                                        f"💡 **USER ACTION REQUIRED:**\n" +
                                        f"Please use the exact project name: get_issue_types with project='{actual_project_name}'"
                                }
                            ],
                            "isError": True
                        }
                    
                    if available_projects:
                        projects_list = "\n".join([f"  - {p}" for p in available_projects])
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"❌ Project '{project}' does not exist in the selected organization.\n\n" +
                                        f"📋 Available projects:\n{projects_list}\n\n" +
                                        f"💡 **USER ACTION REQUIRED:**\n" +
                                        f"• If the project was just created, wait 1-2 minutes and try again\n" +
                                        f"• Use one of the available project names above\n" +
                                        f"• Create a new project using create_project tool\n\n" +
                                        f"Example: get_issue_types with project='{available_projects[0]}'"
                                }
                            ],
                            "isError": True
                        }
                    else:
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"❌ Project '{project}' does not exist and no projects found in the organization.\n\n" +
                                        f"💡 **USER ACTION REQUIRED:**\n" +
                                        f"Please create a project first using create_project tool.\n\n" +
                                        f"Example: create_project with projectKey='{project}' and projectName='{project}'"
                                }
                            ],
                            "isError": True
                        }
            else:
                logger.warning(f"Could not fetch projects list: {projects_response.status_code}")
                # Continue with original request if we can't fetch projects list
        except Exception as e:
            logger.warning(f"Error validating project existence: {e}")
            # Continue with original request if validation fails

        # Now try to get work item types for the project
        encoded_project = urllib.parse.quote(str(project))
        response = self._make_api_request('GET', f'/{encoded_project}/_apis/wit/workitemtypes?api-version=7.1', timeout=15)

        if response.status_code == 200:
            types_data = response.json()
            types = [wt["name"] for wt in types_data.get("value", [])]

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"✅ Available work item types for project '{project}':\n" +
                            "\n".join([f"  - {t}" for t in types]) + 
                            f"\n\n💡 You can now create work items using create_issue tool with any of these types."
                    }
                ]
            }
        elif response.status_code == 404:
            # Handle 404 specifically with helpful message
            try:
                # Try to get available projects for a better error message
                projects_response = self._make_api_request('GET', '/_apis/projects?api-version=7.1', timeout=15)
                if projects_response.status_code == 200:
                    projects_data = projects_response.json()
                    available_projects = [p.get("name") for p in projects_data.get("value", [])]
                    
                    if available_projects:
                        projects_list = "\n".join([f"  - {p}" for p in available_projects])
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"❌ Project '{project}' not found.\n\n" +
                                        f"📋 Available projects in this organization:\n{projects_list}\n\n" +
                                        f"💡 **USER ACTION REQUIRED:**\n" +
                                        f"• If the project was recently created, wait 1-2 minutes for ADO to finish provisioning\n" +
                                        f"• Use get_all_projects to refresh the project list\n" +
                                        f"• Use one of the available project names above\n\n" +
                                        f"Example: get_issue_types with project='{available_projects[0]}'"
                                }
                            ],
                            "isError": True
                        }
                    else:
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"❌ Project '{project}' not found and no projects exist in this organization.\n\n" +
                                        f"💡 **USER ACTION REQUIRED:**\n" +
                                        f"Please create a project first using create_project tool.\n\n" +
                                        f"Example: create_project with projectKey='{project}' and projectName='{project}'"
                                }
                            ],
                            "isError": True
                        }
            except Exception as e:
                logger.error(f"Error getting projects for 404 response: {e}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Project '{project}' does not exist.\n\n" +
                            f"💡 **Possible Causes & Solutions:**\n" +
                            f"• **Recently created project**: Wait 1-2 minutes for ADO provisioning to complete\n" +
                            f"• **Project name mismatch**: Use get_all_projects to see exact project names\n" +
                            f"• **Project doesn't exist**: Create it using create_project tool\n\n" +
                            f"**Next Steps:**\n" +
                            f"1. Run get_all_projects to see available projects\n" +
                            f"2. Use the exact project name from the list\n" +
                            f"3. Or create a new project if needed"
                    }
                ],
                "isError": True
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Failed to get work item types: {response.status_code}\n\n" +
                            f"Error details: {response.text}\n\n" +
                            f"💡 This might be due to:\n" +
                            f"• Project '{project}' doesn't exist\n" +
                            f"• Insufficient permissions\n" +
                            f"• Network connectivity issues"
                    }
                ],
                "isError": True
            }

    async def _search_issues(self, arguments: Dict) -> Dict:
        """Search for work items."""
        # Check if session is authenticated (only need access token, not URL yet)
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Authentication required. Please call 'authenticate' first."}],
                "isError": True
            }

        # Check if organization is selected
        if not self.oauth_manager.ado_url:
            return {
                "content": [{"type": "text", "text": "No organization selected. Please use select_organization first."}],
                "isError": True
            }

        project = arguments.get('project')
        query = arguments.get('query', 'SELECT [System.Id], [System.Title] FROM WorkItems')

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

        encoded_project = urllib.parse.quote(str(project))
        payload = {"query": query}
        response = self._make_api_request('POST', f'/{encoded_project}/_apis/wit/wiql?api-version=7.1', json=payload, timeout=15)

        if response.status_code == 200:
            data = response.json()
            work_items = data.get("workItems", [])

            if work_items:
                items_text = "\n".join([f"- #{wi['id']}" for wi in work_items[:10]])
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Found {len(work_items)} work items:\n{items_text}"
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "No work items found"
                        }
                    ]
                }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Failed to search work items: {response.status_code} {response.text}"
                    }
                ],
                "isError": True
            }

    async def _get_issue(self, arguments: Dict) -> Dict:
        """Get a specific work item."""
        # Check if session is authenticated (only need access token, not URL yet)
        if not self.session_authenticated or not (self.oauth_manager and self.oauth_manager.access_token):
            return {
                "content": [{"type": "text", "text": "Authentication required. Please call 'authenticate' first."}],
                "isError": True
            }

        # Check if organization is selected
        if not self.oauth_manager.ado_url:
            return {
                "content": [{"type": "text", "text": "No organization selected. Please use select_organization first."}],
                "isError": True
            }

        issue_id = arguments.get('issueId')

        if not issue_id:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Issue ID parameter is required"
                    }
                ],
                "isError": True
            }

        response = self._make_api_request('GET', f'/_apis/wit/workitems/{issue_id}?api-version=7.1', timeout=15)

        if response.status_code == 200:
            work_item = response.json()
            fields = work_item.get("fields", {})

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Work Item #{issue_id}:\n" +
                            f"Title: {fields.get('System.Title', 'N/A')}\n" +
                            f"State: {fields.get('System.State', 'N/A')}\n" +
                            f"Type: {fields.get('System.WorkItemType', 'N/A')}"
                    }
                ]
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Failed to get work item: {response.status_code} {response.text}"
                    }
                ],
                "isError": True
            }

async def handle_request(request_line: str, server: ADOMCPServer) -> Optional[Dict]:
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
    server = ADOMCPServer()
    logger.info("ADO MCP Server started")

    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break

            response = await handle_request(line, server)
            if response:
                print(json.dumps(response), flush=True)

    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())