"""Node 5: Adapt content for each platform (LinkedIn, Facebook, Instagram)."""
import logging
import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.ai.state import GenerationState, PlatformContent
from app.services.ai.router import get_model_router

logger = logging.getLogger(__name__)

ADAPTATION_PROMPT = """You are a social media expert. Adapt the core content for each platform.

Core Content:
{core_content}

Long-form Version (for LinkedIn/Blog):
{long_text}

Brand Context:
- Company: {company_name}
- Tone: {tone}
- Tagline: {tagline}

Platform Requirements:
{platform_specs}

For EACH platform, create:
1. Platform-optimized text
2. Relevant hashtags (5-15)
3. Character count

Return ONLY valid JSON array:
[
  {
    "platform": "linkedin",
    "text": "string",
    "hashtags": ["string"],
    "character_count": integer
  },
  {
    "platform": "facebook",
    "text": "string",
    "hashtags": ["string"],
    "character_count": integer
  },
  {
    "platform": "instagram",
    "text": "string",
    "hashtags": ["string"],
    "character_count": integer
  }
]"""

PLATFORM_SPECS = """
LinkedIn:
- Professional audience, longer format OK (up to 3000 chars)
- Thought leadership style, industry insights
- 3-5 relevant hashtags
- Line breaks for readability

Facebook:
- General audience, conversational
- Medium length (up to 2000 chars)
- Engaging, community-focused
- 3-8 hashtags
- Emojis encouraged

Instagram:
- Visual-first, caption supports image
- Short, punchy (up to 2200 chars but keep concise)
- 10-15 hashtags (mix popular + niche)
- Call-to-action encouraged
- Line breaks and emojis
"""


async def adapt_platforms_node(state: GenerationState) -> GenerationState:
    """Adapt the generated content for each target platform."""
    job = state.job_input
    brand = state.brand_kit
    
    if not job.platforms:
        state.error = "No platforms specified"
        return state
    
    core_content = state.generated_text or state.long_text or ""
    long_text = state.long_text or core_content
    
    # Build platform specs for requested platforms
    requested_specs = []
    for platform in job.platforms:
        if platform == "linkedin":
            requested_specs.append("LinkedIn: Professional, up to 3000 chars, 3-5 hashtags")
        elif platform == "facebook":
            requested_specs.append("Facebook: Conversational, up to 2000 chars, 3-8 hashtags")
        elif platform == "instagram":
            requested_specs.append("Instagram: Visual-first, concise, 10-15 hashtags")
    
    router = get_model_router()
    
    messages = [
        SystemMessage(content=ADAPTATION_PROMPT.format(
            core_content=core_content[:2000],
            long_text=long_text[:3000],
            company_name=brand.company_name,
            tone=brand.tone or "professional",
            tagline=brand.tagline or "N/A",
            platform_specs="\n".join(requested_specs),
        )),
        HumanMessage(content="Adapt for each platform."),
    ]
    
    try:
        result = await router.ainvoke(messages, require_json=True)
        platforms_data = json.loads(result.generations[0].text)
        
        platform_contents = []
        for pc_data in platforms_data:
            if pc_data.get("platform") in job.platforms:
                platform_contents.append(PlatformContent(**pc_data))
        
        state.platform_contents = platform_contents
        
    except Exception as e:
        logger.error(f"Platform adaptation failed: {e}")
        state.platform_contents = _create_fallback_adaptations(job, brand, core_content, long_text)
    
    state.current_step = "awaiting_review"
    state.progress = 95
    state.awaiting_review = True
    
    return state


def _create_fallback_adaptations(job, brand, core_content, long_text) -> list:
    """Create simple fallback adaptations."""
    from app.services.ai.state import PlatformContent
    
    adaptations = []
    
    if "linkedin" in job.platforms:
        adaptations.append(PlatformContent(
            platform="linkedin",
            text=long_text[:2800],
            hashtags=_extract_hashtags(job.keywords, brand.company_name, 5),
            character_count=min(len(long_text), 2800),
        ))
    
    if "facebook" in job.platforms:
        adaptations.append(PlatformContent(
            platform="facebook",
            text=core_content[:1800] + "\n\nWhat do you think? 👇",
            hashtags=_extract_hashtags(job.keywords, brand.company_name, 6),
            character_count=min(len(core_content) + 20, 1800),
        ))
    
    if "instagram" in job.platforms:
        adaptations.append(PlatformContent(
            platform="instagram",
            text=core_content[:200] + " ✨",
            hashtags=_extract_hashtags(job.keywords, brand.company_name, 12),
            character_count=min(len(core_content) + 10, 2200),
        ))
    
    return adaptations


def _extract_hashtags(keywords: list, company_name: str, max_tags: int) -> list:
    """Extract hashtags from keywords and company name."""
    tags = []
    company_tag = "".join(word.capitalize() for word in company_name.split() if word.isalnum())
    if company_tag:
        tags.append(company_tag)
    
    for kw in keywords:
        tag = "".join(word.capitalize() for word in kw.split() if word.isalnum())
        if tag and tag not in tags:
            tags.append(tag)
    
    generic = ["ContentMarketing", "AI", "Marketing", "Business", "Growth"]
    for g in generic:
        if g not in tags and len(tags) < max_tags:
            tags.append(g)
    
    return tags[:max_tags]