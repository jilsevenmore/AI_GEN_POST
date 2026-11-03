"""Publisher interface and Buffer implementation."""
import abc
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

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


class BufferPublisher(Publisher):
    """Buffer API publisher implementation."""
    
    BASE_URL = "https://api.bufferapp.com/1"
    OAUTH_AUTH_URL = "https://publish.buffer.com/oauth2/authorize"
    OAUTH_TOKEN_URL = "https://api.bufferapp.com/1/oauth2/token.json"
    
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
    
    async def get_authorization_url(self, state: str) -> str:
        """Generate Buffer OAuth authorization URL with PKCE."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "posts.write,profiles.read",
            "state": state,
        }
        
        # Buffer doesn't support PKCE natively, but we include state for CSRF protection
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.OAUTH_AUTH_URL}?{query}"
    
    async def exchange_code(self, code: str, state: str) -> ChannelConnection:
        """Exchange OAuth code for access/refresh tokens."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "grant_type": "authorization_code",
        }
        
        response = await self.client.post(self.OAUTH_TOKEN_URL, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        # Get user's profiles to determine platform
        profiles = await self._get_profiles(token_data["access_token"])
        
        # Create channel connections for each profile
        # For now, we'll return the first one - in production you'd create multiple
        primary_profile = profiles[0]
        
        return ChannelConnection(
            platform=primary_profile["service"],
            external_account_id=primary_profile["id"],
            account_name=primary_profile.get("formatted_username", primary_profile["service_username"]),
            access_token_encrypted=self._encrypt(token_data["access_token"]),
            refresh_token_encrypted=self._encrypt(token_data.get("refresh_token", "")),
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600)),
            is_active=True,
        )
    
    async def _get_profiles(self, access_token: str) -> List[Dict]:
        """Get connected profiles from Buffer."""
        response = await self.client.get(
            "/profiles.json",
            params={"access_token": access_token},
        )
        response.raise_for_status()
        return response.json()
    
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
        
        response = await self.client.post(self.OAUTH_TOKEN_URL, data=data)
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
    
    async def publish(
        self,
        channel: ChannelConnection,
        content: Content,
        image_url: str,
        text: str,
        schedule_at: Optional[datetime] = None,
    ) -> PublishResult:
        """Publish content to Buffer."""
        access_token = self._get_access_token(channel)
        
        # Prepare payload
        payload = {
            "access_token": access_token,
            "profile_ids[]": channel.external_account_id,
            "text": text,
            "media[photo]": image_url,
        }
        
        if schedule_at:
            # Buffer uses Unix timestamp
            payload["scheduled_at"] = int(schedule_at.timestamp())
        else:
            payload["now"] = "true"
        
        try:
            response = await self.client.post(
                "/updates/create.json",
                data=payload,
            )
            
            if response.status_code == 401:
                # Token expired, try refresh
                return PublishResult(
                    success=False,
                    error="Token expired",
                    error_code="TOKEN_EXPIRED",
                )
            
            response.raise_for_status()
            result = response.json()
            
            # Buffer returns updates array
            updates = result.get("updates", [])
            if updates:
                external_id = updates[0].get("id")
                return PublishResult(
                    success=True,
                    external_post_id=external_id,
                )
            
            return PublishResult(
                success=False,
                error="No update ID returned",
                error_code="NO_UPDATE_ID",
            )
            
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", str(e))
            except:
                error_detail = str(e)
            
            # Categorize errors
            if e.response.status_code == 429:
                error_code = "RATE_LIMITED"
            elif e.response.status_code == 400:
                if "image" in error_detail.lower():
                    error_code = "IMAGE_REJECTED"
                elif "media" in error_detail.lower():
                    error_code = "MEDIA_FETCH_FAILED"
                else:
                    error_code = "INVALID_REQUEST"
            elif e.response.status_code == 401:
                error_code = "TOKEN_EXPIRED"
            elif e.response.status_code == 403:
                error_code = "PERMISSION_DENIED"
            else:
                error_code = "API_ERROR"
            
            return PublishResult(
                success=False,
                error=f"Buffer API error: {error_detail}",
                error_code=error_code,
            )
        
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return PublishResult(
                success=False,
                error=f"Publish failed: {str(e)}",
                error_code="UNKNOWN_ERROR",
            )


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