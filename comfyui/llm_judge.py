"""
LLM as Judge for Food Photography
Uses GPT-4V or Claude to evaluate and select the best generated image.
"""

import os
import json
from typing import List, Dict, Optional

# Try OpenAI first, fallback to Anthropic
try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


JUDGE_PROMPT = """You are an expert food photography critic. Evaluate these {num_images} AI-generated images of "{item_name}".

Rate each image on these criteria (1-10 scale):
1. **Appetizing Appeal**: Does it make you want to eat it? Natural colors, proper textures, inviting presentation.
2. **Realism/Authenticity**: Does it look like real food photography? No AI artifacts, weird shapes, or unnatural elements.
3. **Composition/Lighting**: Professional photography quality? Good lighting, proper depth of field, balanced composition.
4. **Technical Quality**: Sharp focus, no blur, proper exposure, no visual defects.

Return your evaluation as valid JSON in this exact format:
{{
  "best_index": 0,
  "scores": [
    {{"appetizing": 8, "realism": 7, "composition": 9, "technical": 8, "total": 32}},
    {{"appetizing": 6, "realism": 8, "composition": 7, "technical": 7, "total": 28}}
  ],
  "reasoning": "Brief explanation of why the best image was chosen",
  "issues": ["List any problems noticed in rejected images"]
}}

The best_index should be the 0-based index of the highest-scoring image."""


def judge_images_openai(
    images_base64: List[str], item_name: str, api_key: Optional[str] = None
) -> Dict:
    """Use GPT-4V to judge images."""
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    # Build content with all images
    content = [
        {
            "type": "text",
            "text": JUDGE_PROMPT.format(
                num_images=len(images_base64), item_name=item_name
            ),
        }
    ]

    for i, img_b64 in enumerate(images_base64):
        content.append({"type": "text", "text": f"Image {i + 1}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high",
                },
            }
        )

    response = client.chat.completions.create(
        model="gpt-5-mini",  # GPT-4o has vision capabilities
        messages=[{"role": "user", "content": content}],
        max_tokens=1000,
        temperature=0.3,
    )

    # Parse JSON from response
    result_text = response.choices[0].message.content

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def judge_images_anthropic(
    images_base64: List[str], item_name: str, api_key: Optional[str] = None
) -> Dict:
    """Use Claude to judge images."""
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    # Build content with all images
    content = []

    for i, img_b64 in enumerate(images_base64):
        content.append({"type": "text", "text": f"Image {i + 1}:"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": JUDGE_PROMPT.format(
                num_images=len(images_base64), item_name=item_name
            ),
        }
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": content}],
    )

    # Parse JSON from response
    result_text = response.content[0].text

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def judge_images(
    images_base64: List[str],
    item_name: str,
    provider: str = "auto",
    api_key: Optional[str] = None,
) -> Dict:
    """
    Judge multiple generated images and select the best one.

    Args:
        images_base64: List of base64-encoded images
        item_name: Name of the food item for context
        provider: "openai", "anthropic", or "auto" (tries openai first)
        api_key: Optional API key (uses env var if not provided)

    Returns:
        {
            "best_index": int,
            "scores": [...],
            "reasoning": str,
            "issues": [...]
        }
    """
    if len(images_base64) == 1:
        # Only one image, no judging needed
        return {
            "best_index": 0,
            "scores": [
                {
                    "appetizing": 0,
                    "realism": 0,
                    "composition": 0,
                    "technical": 0,
                    "total": 0,
                }
            ],
            "reasoning": "Only one image generated - no comparison needed",
            "issues": [],
        }

    # Determine provider
    if provider == "auto":
        if HAS_OPENAI and (api_key or os.environ.get("OPENAI_API_KEY")):
            provider = "openai"
        elif HAS_ANTHROPIC and (api_key or os.environ.get("ANTHROPIC_API_KEY")):
            provider = "anthropic"
        else:
            raise ValueError(
                "No LLM provider available. Install openai or anthropic and set API key."
            )

    try:
        if provider == "openai":
            if not HAS_OPENAI:
                raise ImportError("openai package not installed")
            return judge_images_openai(images_base64, item_name, api_key)
        elif provider == "anthropic":
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package not installed")
            return judge_images_anthropic(images_base64, item_name, api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    except Exception as e:
        print(f"LLM Judge error: {e}")
        # Fallback: return first image as best
        return {
            "best_index": 0,
            "scores": [],
            "reasoning": f"Judge failed with error: {str(e)}. Returning first image.",
            "issues": [str(e)],
            "error": True,
        }
