"""Node 4: Safety check for generated text and image."""
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.ai.state import GenerationState
from app.services.ai.router import get_model_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SAFETY_CHECK_PROMPT = """You are a content safety moderator. Check the generated content for policy violations.

Text to check:
{text}

Image prompt used:
{image_prompt}

Check for:
1. Hate speech, harassment, discrimination
2. Sexual content, nudity
3. Violence, self-harm
4. Illegal activities
5. PII (personal info, addresses, phones)
6. Spam, misleading content
7. Off-brand content (doesn't match company values)

Brand Context:
- Company: {company_name}
- Tone: {tone}

Return ONLY valid JSON:
{{
  "passed": boolean,
  "flags": ["string"],
  "severity": "none|low|medium|high",
  "reasoning": "string"
}}"""


async def safety_check_node(state: GenerationState) -> GenerationState:
    """Run safety check on generated text and image."""
    job = state.job_input
    brand = state.brand_kit
    
    # Combine text for checking
    text_to_check = state.long_text or state.generated_text or ""
    image_prompt = state.image_brief.prompt if state.image_brief else ""
    
    if not text_to_check:
        state.safety_check_passed = True
        state.current_step = "adapting"
        state.progress = 80
        return state

    # Safety check disabled via config — skip LLM moderation, allow content through
    if not settings.ENABLE_SAFETY_CHECK:
        state.safety_check_passed = True
        state.safety_flags = []
        state.current_step = "adapting"
        state.progress = 80
        logger.info(f"Safety check skipped for job {job.job_id} (ENABLE_SAFETY_CHECK=False)")
        return state

    router = get_model_router()
    
    messages = [
        SystemMessage(content=SAFETY_CHECK_PROMPT.format(
            text=text_to_check[:3000],  # Limit length
            image_prompt=image_prompt[:500],
            company_name=brand.company_name,
            tone=brand.tone or "professional",
        )),
        HumanMessage(content="Check this content for safety violations."),
    ]
    
    try:
        result = await router.ainvoke(messages, require_json=True)
        import json
        safety_data = json.loads(result.generations[0].text)
        
        state.safety_check_passed = safety_data.get("passed", True)
        state.safety_flags = safety_data.get("flags", [])

        if not state.safety_check_passed:
            logger.warning(f"Safety check flagged content for job {job.job_id}: {state.safety_flags}")
            # Record flags but do NOT fail generation — content proceeds to review
            # so the user can edit and publish manually.
            state.error = None
        
    except Exception as e:
        logger.error(f"Safety check failed: {e}")
        # Fail open - allow content through but log
        state.safety_check_passed = True
        state.safety_flags = ["safety_check_error"]
    
    state.current_step = "adapting"
    state.progress = 80
    
    return state