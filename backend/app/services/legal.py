"""Legal pages content and endpoints."""
from typing import Optional
from datetime import datetime, timezone

# Privacy Policy
PRIVACY_POLICY = {
    "last_updated": "2026-11-03",
    "version": "1.0",
    "sections": [
        {
            "title": "1. Information We Collect",
            "content": [
                "We collect information you provide directly to us, including:",
                "- Account information: name, email, password (hashed), company name",
                "- Brand kit: company name, tagline, address, logo, colors, tone preferences",
                "- Content inputs: topics, descriptions, keywords, image descriptions",
                "- Generated content: text, images, platform-specific adaptations",
                "- Publishing data: connected social accounts, publish history, scheduling",
                "- Usage data: feature usage, error logs, performance metrics",
            ]
        },
        {
            "title": "2. How We Use Your Information",
            "content": [
                "We use your information to:",
                "- Provide and improve the AI content generation service",
                "- Generate text and images based on your prompts",
                "- Apply your brand kit to generated content",
                "- Publish content to your connected social media accounts",
                "- Store your approved images in the library for reuse",
                "- Enforce usage quotas and billing limits",
                "- Ensure safety and compliance with platform policies",
                "- Communicate with you about service updates",
            ]
        },
        {
            "title": "3. AI Model Providers and Data Sharing",
            "content": [
                "We use multiple AI providers to generate content:",
                "- **OpenRouter (free models)**: Your prompts and brand data may be logged by free model providers for model improvement. You can opt out by enabling 'OpenAI Only' mode in Brand Kit settings.",
                "- **OpenAI (fallback)**: Used when free models are unavailable. Subject to OpenAI's data usage policies.",
                "- **GPT Image 2.5 Sunburst**: Used for image generation. Subject to OpenAI's data usage policies.",
                "We only send the minimum data necessary for generation. We do not sell your data.",
            ]
        },
        {
            "title": 4,
            "title": "4. Data Retention and Deletion",
            "content": [
                "We retain your data as follows:",
                "- Account data: Until you delete your account",
                "- Brand kit: Until you update or delete it",
                "- Generated content: Until you delete it",
                "- Approved images in library: Until you delete them",
                "- Published images: Auto-deleted after 30 days",
                "- Rejected drafts: Auto-deleted after 7 days",
                "- Publish history: 90 days",
                "- Usage logs: 90 days",
                "You can request deletion of your data at any time by contacting support or using the account deletion feature.",
            ]
        },
        {
            "title": "5. Security",
            "content": [
                "We implement appropriate security measures:",
                "- Passwords hashed with bcrypt",
                "- JWT tokens with short expiry (30 min) and rotation",
                "- OAuth tokens encrypted at rest (Fernet)",
                "- Company-level data isolation (row-level security)",
                "- HTTPS/TLS for all communications",
                "- Regular dependency vulnerability scanning",
                "- Prompt injection detection and prevention",
            ]
        },
        {
            "title": "6. Your Rights",
            "content": [
                "You have the right to:",
                "- Access your personal data",
                "- Rectify inaccurate data",
                "- Erase your data (account deletion)",
                "- Restrict processing",
                "- Data portability",
                "- Object to processing",
                "- Lodge a complaint with a supervisory authority",
            ]
        },
        {
            "title": "7. International Transfers",
            "content": [
                "Your data may be processed in the United States and other countries where our providers operate. We ensure appropriate safeguards are in place.",
            ]
        },
        {
            "title": "8. Changes to This Policy",
            "content": [
                "We may update this policy from time to time. We will notify you of material changes via email or in-app notification.",
            ]
        },
        {
            "title": "9. Contact Us",
            "content": [
                "For privacy questions or requests, contact: privacy@aigenpost.com",
            ]
        },
    ]
}


# Terms of Service
TERMS_OF_SERVICE = {
    "last_updated": "2026-11-03",
    "version": "1.0",
    "sections": [
        {
            "title": "1. Acceptance of Terms",
            "content": [
                "By accessing and using AI Blog & Social Post Generator ('the Service'), you agree to be bound by these Terms of Service ('Terms'). If you do not agree, do not use the Service.",
            ]
        },
        {
            "title": "2. Description of Service",
            "content": [
                "The Service provides AI-powered content generation for blogs and social media posts, including text generation, image creation, brand consistency management, and social media publishing via Buffer.",
            ]
        },
        {
            "title": "3. User Accounts",
            "content": [
                "You must provide accurate information and keep credentials secure. You are responsible for all activity under your account. We may terminate accounts for violations.",
            ]
        },
        {
            "title": "4. AI-Generated Content",
            "content": [
                "Content generated by our AI models is provided 'as-is'. You are responsible for reviewing and approving all content before publishing. The Service includes safety checks, but AI can make mistakes. You own the content you generate and approve.",
            ]
        },
        {
            "title": "5. Free Model Data Logging Notice",
            "content": [
                "**IMPORTANT**: When using free OpenRouter models, your prompts and generated content may be logged by the model providers for model improvement purposes. This includes your brand data, prompts, and generated text/images. If you do not want this, enable 'OpenAI Only' mode in your Brand Kit settings, which routes all generation through OpenAI's paid API (subject to OpenAI's data policies).",
            ]
        },
        {
            "title": "6. Social Media Publishing",
            "content": [
                "Publishing to social media platforms (Instagram, Facebook, LinkedIn) is done via Buffer's official API. You must connect your own accounts. You are responsible for complying with each platform's terms of service, community guidelines, and automation policies. We do not guarantee publication success or account safety.",
            ]
        },
        {
            "title": "7. Acceptable Use",
            "content": [
                "You agree not to:",
                "- Generate illegal, harmful, or hateful content",
                "- Impersonate others or misrepresent affiliation",
                "- Spam or abuse social media platforms",
                "- Reverse engineer or extract our models",
                "- Exceed rate limits or quotas",
                "- Use the Service for competitive analysis of our technology",
            ]
        },
        {
            "title": "8. Intellectual Property",
            "content": [
                "You retain ownership of your inputs and approved outputs. We retain ownership of the Service, algorithms, and underlying technology. You grant us a license to use your inputs solely to provide the Service.",
            ]
        },
        {
            "title": "9. Disclaimers",
            "content": [
                "THE SERVICE IS PROVIDED 'AS IS' WITHOUT WARRANTIES OF ANY KIND. WE DO NOT GUARANTEE ACCURACY, RELIABILITY, OR UNINTERRUPTED AVAILABILITY. AI-GENERATED CONTENT MAY CONTAIN ERRORS.",
            ]
        },
        {
            "title": "10. Limitation of Liability",
            "content": [
                "TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE ARE NOT LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES. OUR TOTAL LIABILITY IS LIMITED TO THE AMOUNT YOU PAID IN THE PRECEDING 12 MONTHS.",
            ]
        },
        {
            "title": "11. Termination",
            "content": [
                "We may suspend or terminate your access for violations. You may delete your account at any time. Provisions that should survive termination will survive.",
            ]
        },
        {
            "title": "12. Governing Law",
            "content": [
                "These Terms are governed by the laws of [Jurisdiction]. Disputes will be resolved in [Court/Arbitration].",
            ]
        },
        {
            "title": "13. Contact",
            "content": [
                "For questions about these Terms, contact: legal@aigenpost.com",
            ]
        },
    ]
}


def get_privacy_policy() -> dict:
    return PRIVACY_POLICY


def get_terms_of_service() -> dict:
    return TERMS_OF_SERVICE


def format_legal_page(page: dict) -> str:
    """Format legal page as markdown."""
    lines = [
        f"# {page['title'] if 'title' in page else 'Legal Page'}",
        f"**Last Updated:** {page['last_updated']}",
        f"**Version:** {page['version']}",
        "",
    ]
    
    for section in page["sections"]:
        lines.append(f"## {section['title']}")
        for paragraph in section["content"]:
            lines.append(paragraph)
            lines.append("")
    
    return "\n".join(lines)