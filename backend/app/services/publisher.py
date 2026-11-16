"""Publisher interface and Buffer implementation."""
import abc
import base64
import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.models.channel import ChannelConnection
from app.models.content import Content
from app.models.publish import PublishAttempt
from app.services.scheduled_jobs import reset_daily_quotas

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PublishResult:
    """Result of a publish attempt."""
    success: bool
    external_post_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None  # For categorizing errors


@dataclass
class ChannelInfo:
    """Normalized channel information."""
    id: UUID
    platform: str  # instagram, facebook, linkedin
    external_account_id: str
    account_name: str


class Publisher(abc.ABC):
    """Abstract publisher interface for social media platforms."""
    
    @abc.abstractmethod
    async def publish(
        self,
        channel: ChannelConnection,
        content: Content,
        image_url: str,
        text: str,
        schedule_at: Optional[datetime] = None,
    ) -> PublishResult:
        """Publish content to a channel."""
        pass
    
    @abc.abstractmethod
    async def get_authorization_url(self, state: str) -> str:
        """Get OAuth authorization URL."""
        pass
    
    @abc.abstractmethod
    async def exchange_code(self, code: str, state: str) -> ChannelConnection:
        """Exchange OAuth code for tokens."""
        pass
    
    @abc.abstractmethod
    async def refresh_token(self, channel: ChannelConnection) -> ChannelConnection:
        """Refresh OAuth token."""
        pass
    
    @abc.abstractmethod
    async def disconnect(self, channel: ChannelConnection) -> bool:
        """Disconnect channel."""
        pass
    
    @abc.abstractmethod
    def get_supported_platforms(self) -> List[str]:
        """Get list of supported platforms."""
        pass


# In-memory PKCE store: state -> code_verifier
# In production, use Redis or another shared store for multi-worker deployments.
_pkce_store: Dict[str, str] = {}


class BufferPublisher(Publisher):
    """Buffer API publisher implementation (current GraphQL API)."""
    
    # New Buffer OAuth endpoints
    BASE_URL = "https://api.buffer.com"
    OAUTH_AUTH_URL = "https://auth.buffer.com/auth"
    OAUTH_TOKEN_URL = "https://auth.buffer.com/token"
    
    # OAuth scopes for the current Buffer API
    OAUTH_SCOPES = [
        "posts:write",
        "posts:read",
        "ideas:read",
        "ideas:write",
        "account:read",
        "account:write",
        "offline_access",
    ]
    
    # Platform-specific image aspect ratios
    PLATFORM_ASPECT_RATIOS = {
        "instagram": ["1:1", "4:5", "9:16"],
        "facebook": ["1:1", "4:5", "1.91:1"],
        "linkedin": ["1.91:1", "1:1"],
    }
    
    # Character limits per platform
    PLATFORM_CHAR_LIMITS = {
        "instagram": 2200,
        "facebook": 63206,
        "linkedin": 3000,
    }
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        self.client_id = settings.BUFFER_CLIENT_ID
        self.client_secret = settings.BUFFER_CLIENT_SECRET
        self.redirect_uri = settings.BUFFER_REDIRECT_URI
        self.rate_limit_rpm = settings.BUFFER_RATE_LIMIT_RPM
        
        # Encryption for token storage
        self._fernet = Fernet(encryption_key) if encryption_key else None
        
        # HTTP client with timeout
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
        )
    
    def get_supported_platforms(self) -> List[str]:
        return ["instagram", "facebook", "linkedin"]
    
    def _encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self._fernet:
            return data  # No encryption if key not provided
        return self._fernet.encrypt(data.encode()).decode()
    
    def _decrypt(self, data: str) -> str:
        """Decrypt sensitive data."""
        if not self._fernet:
            return data
        return self._fernet.decrypt(data.encode()).decode()
    
    # ------------------------------------------------------------------
    # PKCE helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _generate_code_verifier() -> str:
        """Generate a random PKCE code verifier."""
        return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
    
    @staticmethod
    def _generate_code_challenge(verifier: str) -> str:
        """Generate SHA-256 code challenge from a verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    
    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------
    async def get_authorization_url(self, state: str) -> str:
        """Generate Buffer OAuth authorization URL with PKCE."""
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        
        # Store the verifier so exchange_code can use it later
        _pkce_store[state] = code_verifier
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.OAUTH_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "consent",
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.OAUTH_AUTH_URL}?{query}"
    
    async def exchange_code(self, code: str, state: str) -> List[ChannelConnection]:
        """Exchange OAuth code for access/refresh tokens, creating channel connections for all channels."""
        code_verifier = _pkce_store.pop(state, None)
        if not code_verifier:
            raise ValueError("No PKCE code verifier found for this state (may have expired)")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }
        
        response = await self.client.post(
            self.OAUTH_TOKEN_URL,
            data=data,
        )
        response.raise_for_status()
        token_data = response.json()
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 3600)
        
        # Get user's channels across all organizations
        channels = await self._get_channels(access_token)
        if not channels:
            raise ValueError("No channels found for this Buffer account")
        
        # Create channel connections for each channel
        channel_connections: List[ChannelConnection] = []
        for channel in channels:
            channel_connections.append(
                ChannelConnection(
                    platform=channel["service"],
                    external_account_id=channel["id"],
                    account_name=channel.get("displayName", channel.get("name", channel["service"])),
                    access_token_encrypted=self._encrypt(access_token),
                    refresh_token_encrypted=self._encrypt(refresh_token) if refresh_token else "",
                    token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                    is_active=True,
                )
            )
        
        logger.info(f"Created {len(channel_connections)} channel connections from OAuth")
        return channel_connections
    
    async def _get_channels(self, access_token: str) -> List[Dict]:
        """Get connected channels from Buffer using GraphQL across all organizations."""
        # First get account info to find organization IDs
        account_query = """
        query Account {
          account {
            id
            email
            organizations {
              id
              name
            }
          }
        }
        """
        
        try:
            account_data = await self._graphql(access_token, account_query)
            account = account_data.get("account", {})
            organizations = account.get("organizations", [])
            
            if not organizations:
                logger.error("No organizations found for this Buffer account")
                return []
            
            all_channels: List[Dict] = []
            
            for org in organizations:
                org_id = org["id"]
                
                channels_query = """
                query GetChannels {
                  channels(input: {
                    organizationId: %s
                  }) {
                    id
                    name
                    displayName
                    service
                    avatar
                    isQueuePaused
                  }
                }
                """ % json_escape(org_id)
                
                data = await self._graphql(access_token, channels_query)
                channels = data.get("channels", [])
                logger.info(f"Organization {org.get('name')} ({org_id}): {len(channels)} channels")
                all_channels.extend(channels)
            
            return all_channels
        except Exception as e:
            logger.error(f"Failed to fetch channels: {e}")
            return []
    
    async def refresh_token(self, channel: ChannelConnection) -> ChannelConnection:
        """Refresh OAuth access token."""
        if not channel.refresh_token_encrypted:
            raise ValueError("No refresh token available")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._decrypt(channel.refresh_token_encrypted),
        }
        
        response = await self.client.post(
            self.OAUTH_TOKEN_URL,
            data=data,
        )
        response.raise_for_status()
        token_data = response.json()
        
        channel.access_token_encrypted = self._encrypt(token_data["access_token"])
        if "refresh_token" in token_data:
            channel.refresh_token_encrypted = self._encrypt(token_data["refresh_token"])
        channel.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))
        channel.updated_at = datetime.now(timezone.utc)
        
        return channel
    
    async def disconnect(self, channel: ChannelConnection) -> bool:
        """Disconnect channel (revoke token if possible)."""
        # Buffer doesn't have a token revocation endpoint
        # Just mark as inactive locally
        channel.is_active = False
        channel.updated_at = datetime.now(timezone.utc)
        return True
    
    def _get_access_token(self, channel: ChannelConnection) -> str:
        """Get decrypted access token."""
        return self._decrypt(channel.access_token_encrypted)
    
    # ------------------------------------------------------------------
    # GraphQL helpers
    # ------------------------------------------------------------------
    async def _graphql(self, access_token: str, query: str) -> Dict:
        """Make a GraphQL request to the Buffer API."""
        response = await self.client.post(
            "",
            json={"query": query},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            error_msgs = [e.get("message", str(e)) for e in data["errors"]]
            raise RuntimeError(f"Buffer GraphQL error: {'; '.join(error_msgs)}")
        
        return data.get("data", {})
    
    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------
    def _select_best_image(self, content: Content, platform: str) -> str:
        """Select best image variant for platform."""
        if not content.image_variants:
            raise ValueError("No image variants available")
        
        # Get preferred aspect ratios for platform
        preferred = self.PLATFORM_ASPECT_RATIOS.get(platform, ["1:1"])
        
        # Find matching variant
        for ratio in preferred:
            for variant in content.image_variants:
                if variant.get("aspect_ratio") == ratio:
                    return variant["url"]
        
        # Fallback to primary or first
        primary_id = content.primary_image_id
        if primary_id:
            for variant in content.image_variants:
                if variant.get("id") == str(primary_id):
                    return variant["url"]
        
        return content.image_variants[0]["url"]
    
    def _get_platform_text(self, content: Content, platform: str) -> str:
        """Get platform-specific text."""
        for pc in content.platform_contents:
            if pc.get("platform") == platform:
                text = pc.get("text", "")
                hashtags = pc.get("hashtags", [])
                if hashtags:
                    text += "\n\n" + " ".join(f"#{h}" for h in hashtags)
                return text
        
        # Fallback to long text
        return content.long_text
    
    def _truncate_text(self, text: str, platform: str) -> str:
        """Truncate text to platform limit."""
        limit = self.PLATFORM_CHAR_LIMITS.get(platform, 3000)
        if len(text) <= limit:
            return text
        return text[:limit - 3] + "..."
    
    def _mode_for_schedule(self, schedule_at: Optional[datetime]) -> str:
        """Determine the sharing mode based on scheduling."""
        return "shareNow" if schedule_at is None else "addToQueue"
    
    async def publish(
        self,
        channel: ChannelConnection,
        content: Content,
        image_url: str,
        text: str,
        schedule_at: Optional[datetime] = None,
    ) -> PublishResult:
        """Publish content to Buffer using the GraphQL API."""
        access_token = self._get_access_token(channel)
        
        # Buffer requires publicly accessible image URLs (not data: URLs)
        if image_url and image_url.startswith("data:"):
            return PublishResult(
                success=False,
                error="Image must be a publicly accessible URL (data URLs/base64 images are not supported by Buffer). Upload the image to a public host and try again.",
                error_code="MEDIA_NOT_PUBLIC",
            )
        
        # Determine scheduling
        if schedule_at:
            mode = "customScheduled"
            scheduling_type = "automatic"
            due_at = schedule_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            mode = "addToQueue"
            scheduling_type = "automatic"
            due_at = None
        
        # Build assets array for image post
        assets_block = ""
        if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
            assets_block = "assets: [{ image: { url: %s } }]," % json_escape(image_url)
        
        # Instagram requires metadata with post type
        metadata_block = ""
        if channel.platform == "instagram":
            # Default to feed post; could be extended to support story/reel
            metadata_block = "metadata: { instagram: { type: post, shouldShareToFeed: true } },"
        
        due_at_block = ""
        if due_at:
            due_at_block = "dueAt: %s," % json_escape(due_at)
        
        mutation = """
        mutation CreatePost {
          createPost(input: {
            text: %s,
            channelId: %s,
            schedulingType: %s,
            mode: %s,
            %s
            %s
            %s
          }) {
            ... on PostActionSuccess {
              post {
                id
                text
              }
            }
            ... on MutationError {
              message
            }
          }
        }
        """ % (
            json_escape(text),
            json_escape(channel.external_account_id),
            scheduling_type,
            mode,
            due_at_block,
            assets_block,
            metadata_block,
        )
        
        async def _attempt(token: str):
            data = await self._graphql(token, mutation)
            result = data.get("createPost", {})
            if "post" in result:
                return PublishResult(success=True, external_post_id=result["post"]["id"])
            return PublishResult(
                success=False,
                error=result.get("message", "No post ID returned"),
                error_code="NO_POST_ID",
            )

        try:
            return await _attempt(access_token)
        except RuntimeError as e:
            error_str = str(e)
            if "401" in error_str or "unauthorized" in error_str.lower():
                # Try one refresh if possible
                try:
                    if channel.refresh_token_encrypted:
                        refreshed = await self.refresh_token(channel)
                        # copy refreshed tokens onto channel object for this attempt
                        channel.access_token_encrypted = refreshed.access_token_encrypted
                        channel.refresh_token_encrypted = refreshed.refresh_token_encrypted
                        channel.token_expires_at = refreshed.token_expires_at
                        return await _attempt(self._get_access_token(channel))
                except Exception as refresh_err:
                    logger.warning(f"Token refresh failed during publish: {refresh_err}")
                return PublishResult(
                    success=False,
                    error="Token expired or unauthorized. Please reconnect Buffer.",
                    error_code="TOKEN_EXPIRED",
                )
            return PublishResult(
                success=False,
                error=f"Buffer API error: {error_str}",
                error_code="API_ERROR",
            )
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return PublishResult(
                success=False,
                error=f"Publish failed: {str(e)}",
                error_code="UNKNOWN_ERROR",
            )


# ------------------------------------------------------------------
# JSON string escaping helper for GraphQL
# ------------------------------------------------------------------
def json_escape(s: str) -> str:
    """Escape a string for safe inclusion in a GraphQL query string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


# Factory for getting publisher
_publisher_instance: Optional[BufferPublisher] = None


def get_publisher() -> BufferPublisher:
    """Get or create the publisher instance."""
    global _publisher_instance
    if _publisher_instance is None:
        # Generate encryption key from settings if available
        encryption_key = None
        if settings.SECRET_KEY:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"buffer_publisher_salt",  # In production, use random salt per deployment
                iterations=100000,
            )
            encryption_key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
        
        _publisher_instance = BufferPublisher(encryption_key=encryption_key)
    
    return _publisher_instance
