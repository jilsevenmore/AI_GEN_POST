"""Legal pages API endpoints."""
from fastapi import APIRouter, Response
from app.services.legal import get_privacy_policy, get_terms_of_service, format_legal_page

router = APIRouter()


@router.get("/privacy", response_class=Response)
async def privacy_policy():
    """Return privacy policy as HTML."""
    policy = get_privacy_policy()
    markdown = format_legal_page(policy)
    
    # Simple markdown to HTML conversion for display
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy - AI Gen Post</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; color: #1f2937; }}
        h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
        h2 {{ color: #374151; margin-top: 2rem; }}
        p {{ margin: 1rem 0; }}
        ul {{ padding-left: 1.5rem; }}
        li {{ margin: 0.5rem 0; }}
        strong {{ color: #111827; }}
        .meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 2rem; }}
        .notice {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 0.5rem; padding: 1rem; margin: 1rem 0; }}
    </style>
</head>
<body>
    <h1>Privacy Policy</h1>
    <div class="meta">Last Updated: {policy['last_updated']} | Version: {policy['version']}</div>
"""
    
    for section in policy["sections"]:
        html += f"<h2>{section['title']}</h2>"
        for paragraph in section["content"]:
            # Highlight important notices
            if "IMPORTANT" in paragraph or "important" in paragraph.lower():
                html += f'<div class="notice">{paragraph}</div>'
            else:
                html += f"<p>{paragraph}</p>"
    
    html += """</body></html>"""
    
    return Response(content=html, media_type="text/html")


@router.get("/terms", response_class=Response)
async def terms_of_service():
    """Return terms of service as HTML."""
    terms = get_terms_of_service()
    markdown = format_legal_page(terms)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms of Service - AI Gen Post</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 2rem; color: #1f2937; }}
        h1 {{ color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
        h2 {{ color: #374151; margin-top: 2rem; }}
        p {{ margin: 1rem 0; }}
        ul {{ padding-left: 1.5rem; }}
        li {{ margin: 0.5rem 0; }}
        strong {{ color: #111827; }}
        .meta {{ color: #6b7280; font-size: 0.875rem; margin-bottom: 2rem; }}
        .notice {{ background: #fef3c7; border: 1px solid #f59e0b; border-radius: 0.5rem; padding: 1rem; margin: 1rem 0; }}
    </style>
</head>
<body>
    <h1>Terms of Service</h1>
    <div class="meta">Last Updated: {terms['last_updated']} | Version: {terms['version']}</div>
"""
    
    for section in terms["sections"]:
        html += f"<h2>{section['title']}</h2>"
        for paragraph in section["content"]:
            if "IMPORTANT" in paragraph or "important" in paragraph.lower():
                html += f'<div class="notice">{paragraph}</div>'
            else:
                html += f"<p>{paragraph}</p>"
    
    html += """</body></html>"""
    
    return Response(content=html, media_type="text/html")


@router.get("/privacy/markdown")
async def privacy_policy_markdown():
    """Return privacy policy as raw markdown."""
    policy = get_privacy_policy()
    return {"markdown": format_legal_page(policy)}


@router.get("/terms/markdown")
async def terms_of_service_markdown():
    """Return terms of service as raw markdown."""
    terms = get_terms_of_service()
    return {"markdown": format_legal_page(terms)}