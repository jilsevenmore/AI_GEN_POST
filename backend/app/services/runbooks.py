"""Runbooks for operational incidents."""

RUNBOOKS = {
    "expired_keys": {
        "title": "Expired API Keys / OAuth Tokens",
        "severity": "critical",
        "description": "One or more API keys or OAuth tokens have expired, causing service failures.",
        "symptoms": [
            "401 Unauthorized errors from external APIs",
            "Publish jobs failing with TOKEN_EXPIRED",
            "AI generation failing with authentication errors",
            "Buffer channel showing as disconnected",
        ],
        "diagnosis": [
            "Check monitoring alerts for TOKEN_EXPIRED error codes",
            "Verify token expiration timestamps in database",
            "Check if automatic token refresh is failing",
            "Review provider status pages for known issues",
        ],
        "resolution": [
            "1. For Buffer: User must re-authenticate via /publish/buffer/connect",
            "2. For OpenAI/OpenRouter: Update API key in .env and restart service",
            "3. For Cloudinary: Update credentials in .env and restart service",
            "4. Verify new tokens work by running test API call",
            "5. Monitor for 15 minutes to confirm resolution",
        ],
        "prevention": [
            "Set up monitoring alerts for token expiration (7 days before)",
            "Implement proactive token refresh (refresh at 80% TTL)",
            "Use key rotation strategy with overlapping validity",
            "Document key expiration dates in secrets manager",
        ],
        "contacts": ["Backend Engineer", "DevOps"],
        "escalation": "If unable to resolve in 30 min, escalate to Engineering Lead",
    },
    
    "provider_outage": {
        "title": "AI Provider Outage (OpenAI / OpenRouter / Buffer)",
        "severity": "critical",
        "description": "External AI provider is experiencing downtime or degraded performance.",
        "symptoms": [
            "High error rates from AI generation (5xx, timeouts)",
            "Circuit breaker triggering (fallback to OpenAI)",
            "Increased job queue depth",
            "User complaints about slow/failing generations",
        ],
        "diagnosis": [
            "Check provider status page (status.openai.com, status.openrouter.ai, status.buffer.com)",
            "Check monitoring for increased error rates and latency",
            "Verify circuit breaker status in metrics",
            "Check if fallback is working (OpenAI fallback for OpenRouter)",
        ],
        "resolution": [
            "1. Enable circuit breaker if not already (automatic)",
            "2. Increase job timeouts temporarily",
            "3. If OpenRouter down: ensure OpenAI fallback is working",
            "4. If OpenAI down: consider reducing free model usage, queue jobs",
            "5. If Buffer down: pause publishing queue, notify users",
            "6. Communicate status to users via status page / in-app banner",
            "7. Monitor provider status for recovery",
            "8. After recovery: verify normal operation, clear backlog",
        ],
        "prevention": [
            "Multi-provider strategy (OpenRouter + OpenAI)",
            "Circuit breaker with automatic fallback",
            "Queue-based architecture for async processing",
            "Provider health checks every 5 minutes",
            "Status page integration for user communication",
        ],
        "contacts": ["Backend Engineer", "DevOps", "Engineering Lead"],
        "escalation": "If outage > 1 hour, escalate to CTO",
    },
    
    "failed_publishing": {
        "title": "Publishing Failures / Buffer API Issues",
        "severity": "high",
        "description": "Posts failing to publish to social media platforms via Buffer.",
        "symptoms": [
            "Publish attempts stuck in 'retrying' or 'failed'",
            "Rate limit errors (429) from Buffer",
            "Image fetch failures (Cloudinary links rejected)",
            "Token expired errors during publish",
            "User reports posts not appearing",
        ],
        "diagnosis": [
            "Check /publish/queue/stats for dead letter queue depth",
            "Check publish attempt error codes (RATE_LIMITED, TOKEN_EXPIRED, IMAGE_REJECTED)",
            "Verify Buffer API status",
            "Check Cloudinary credit usage and link accessibility",
            "Verify channel tokens haven't expired",
        ],
        "resolution": [
            "For RATE_LIMITED: Wait for rate limit window, jobs auto-retry",
            "For TOKEN_EXPIRED: User must re-authenticate Buffer",
            "For IMAGE_REJECTED: Check Cloudinary credits, verify image URLs accessible",
            "For MEDIA_FETCH_FAILED: Verify Cloudinary links work, consider R2 fallback",
            "For PERMISSION_DENIED: Check Buffer app permissions, user account status",
            "Manual retry: POST /publish/attempts/{id}/retry",
            "Clear dead letter queue after fixing root cause",
        ],
        "prevention": [
            "Rate limiting at 80% of Buffer limits",
            "Proactive token refresh before expiry",
            "Cloudinary credit alerts at 70%/90%",
            "Image URL validation before enqueueing",
            "Dead letter queue monitoring alert",
        ],
        "contacts": ["Backend Engineer", "DevOps"],
        "escalation": "If >10% publish failure rate for 15 min, escalate",
    },
    
    "cloudinary_credit_exhaustion": {
        "title": "Cloudinary Credit Exhaustion",
        "severity": "high",
        "description": "Cloudinary free tier credits exhausted, images stop loading.",
        "symptoms": [
            "Images not loading in frontend (403/404 from Cloudinary)",
            "Publish failures due to image fetch failures",
            "Cloudinary dashboard shows 0 credits remaining",
            "New uploads failing",
        ],
        "diagnosis": [
            "Check Cloudinary dashboard for credit usage",
            "Check monitoring alerts for credit thresholds (70%/90%)",
            "Verify cleanup job is running (deletes old images)",
            "Check if any runaway process is uploading excessively",
        ],
        "resolution": [
            "1. Immediate: Enable R2/Tigris fallback for image serving",
            "2. Run cleanup job manually: cleanup_old_images()",
            "3. Purchase additional Cloudinary credits or upgrade plan",
            "4. Temporarily reduce image quality/variants to save credits",
            "5. Monitor credit usage hourly until stabilized",
        ],
        "prevention": [
            "Alerts at 70% and 90% credit usage",
            "Automatic cleanup: published >30 days, drafts >7 days",
            "Limit image variants to 3 per generation",
            "Use optimized formats (WebP) and compression",
            "Quota tied to credits (1 generation = X credits)",
            "R2/Tigris fallback configured and tested",
        ],
        "contacts": ["Backend Engineer", "DevOps", "Engineering Lead"],
        "escalation": "If credits exhausted during campaign, escalate immediately",
    },
}


def get_runbook(name: str) -> dict:
    """Get a specific runbook."""
    return RUNBOOKS.get(name, {"error": f"Runbook '{name}' not found"})


def list_runbooks() -> List[str]:
    """List all available runbooks."""
    return list(RUNBOOKS.keys())


def format_runbook(name: str) -> str:
    """Format runbook as markdown."""
    rb = get_runbook(name)
    if "error" in rb:
        return f"# Error\n{rb['error']}"
    
    lines = [
        f"# {rb['title']}",
        f"**Severity:** {rb['severity'].upper()}",
        f"**Description:** {rb['description']}",
        "",
        "## Symptoms",
    ]
    for s in rb["symptoms"]:
        lines.append(f"- {s}")
    
    lines.extend(["", "## Diagnosis Steps"])
    for d in rb["diagnosis"]:
        lines.append(f"- {d}")
    
    lines.extend(["", "## Resolution Steps"])
    for r in rb["resolution"]:
        lines.append(f"- {r}")
    
    lines.extend(["", "## Prevention"])
    for p in rb["prevention"]:
        lines.append(f"- {p}")
    
    lines.extend(["", "## Contacts"])
    for c in rb["contacts"]:
        lines.append(f"- {c}")
    
    lines.extend(["", "## Escalation"])
    lines.append(rb["escalation"])
    
    return "\n".join(lines)