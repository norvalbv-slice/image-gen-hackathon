"""
Scene Extractor for Reference Images
Uses GPT-4V or Claude to analyze a reference food photo and extract scene characteristics.
"""

import os
import json
from typing import Dict, Optional

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


EXTRACTION_PROMPT = """You are an expert food photography analyst. Analyze this food photograph and extract the scene characteristics for recreating similar images.

Extract the following details:

1. **name**: Give this style a short descriptive name (e.g., "Warm Italian Trattoria", "Modern Minimalist Cafe")

2. **background**: Describe the surface, table, backdrop. Be specific about materials, colors, textures.
   Example: "rustic dark wooden table with visible grain, blurred brick wall in background"

3. **lighting**: Describe the lighting setup - direction, warmth, shadows, intensity.
   Example: "warm directional light from upper left, soft shadows, golden hour warmth"

4. **mood**: The atmosphere and feeling conveyed.
   Example: "cozy, authentic, inviting, family-style"

5. **props**: Other elements in the frame besides the main food item.
   Example: "white linen napkin, scattered fresh basil leaves, olive oil bottle blurred in background"

6. **realism**: Describe texture qualities and authenticity markers that make it look real.
   Example: "natural food imperfections, authentic cheese melt with uneven texture, slight char on crust edges"

7. **composition**: Camera angle and framing style.
   Example: "45-degree angle from corner, shallow depth of field, subject fills 60% of frame"

Return your analysis as valid JSON in this exact format:
{
  "name": "Style Name Here",
  "background": "detailed background description",
  "lighting": "lighting description",
  "mood": "mood and atmosphere",
  "props": "props and additional elements",
  "realism": "authenticity markers and texture qualities",
  "variations": [
    {"angle": "primary angle from image", "focus": "focus point", "depth": "depth of field"},
    {"angle": "alternative angle suggestion", "focus": "different focus", "depth": "depth variation"},
    {"angle": "third angle option", "focus": "another focus point", "depth": "depth style"},
    {"angle": "fourth angle option", "focus": "macro detail", "depth": "ultra shallow"}
  ]
}

The variations array should include the angle from the reference image first, then suggest 3 alternative angles that would work well with this scene style."""


def extract_scene_openai(image_base64: str, api_key: Optional[str] = None) -> Dict:
    """Use GPT-4V to extract scene from reference image."""
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    content = [
        {"type": "text", "text": EXTRACTION_PROMPT},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_base64}",
                "detail": "high",
            },
        },
    ]

    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[{"role": "user", "content": content}],
        max_tokens=1500,
        temperature=0.3,
    )

    result_text = response.choices[0].message.content

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def extract_scene_anthropic(image_base64: str, api_key: Optional[str] = None) -> Dict:
    """Use Claude to extract scene from reference image."""
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_base64,
            },
        },
        {"type": "text", "text": EXTRACTION_PROMPT},
    ]

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}],
    )

    result_text = response.content[0].text

    # Extract JSON from response (handle markdown code blocks)
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def extract_scene_from_image(
    image_base64: str,
    provider: str = "auto",
    api_key: Optional[str] = None,
) -> Dict:
    """
    Analyze a reference food photo and extract scene characteristics.

    Args:
        image_base64: Base64-encoded reference image
        provider: "openai", "anthropic", or "auto" (tries openai first)
        api_key: Optional API key (uses env var if not provided)

    Returns:
        {
            "name": "Style Name",
            "background": "...",
            "lighting": "...",
            "mood": "...",
            "props": "...",
            "realism": "...",
            "variations": [...]
        }
    """
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
            return extract_scene_openai(image_base64, api_key)
        elif provider == "anthropic":
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package not installed")
            return extract_scene_anthropic(image_base64, api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    except json.JSONDecodeError as e:
        print(f"Scene extraction JSON parse error: {e}")
        # Return a default scene if parsing fails
        return get_default_extracted_scene()
    except Exception as e:
        print(f"Scene extraction error: {e}")
        return get_default_extracted_scene()


def get_default_extracted_scene() -> Dict:
    """Return a default scene config if extraction fails."""
    return {
        "name": "Default Food Photography",
        "background": "clean neutral surface, simple backdrop",
        "lighting": "soft natural lighting from the side",
        "mood": "clean, appetizing, professional",
        "props": "minimal props, focus on food",
        "realism": "authentic food texture, natural imperfections",
        "variations": [
            {"angle": "overhead flat lay", "focus": "entire dish", "depth": "medium"},
            {"angle": "45-degree angle", "focus": "front of dish", "depth": "shallow"},
            {"angle": "eye level", "focus": "center", "depth": "shallow"},
            {"angle": "close-up detail", "focus": "texture", "depth": "ultra shallow"},
        ],
        "extraction_failed": True,
    }


def build_prompt_from_extracted_scene(
    item_name: str,
    item_description: str,
    extracted_scene: Dict,
    variation_index: int = 0,
) -> Dict:
    """
    Build a generation prompt using an extracted scene config.

    Args:
        item_name: Name of the food item to generate
        item_description: Description/ingredients
        extracted_scene: Scene config from extract_scene_from_image()
        variation_index: Which variation to use (0-3)

    Returns:
        {
            "prompt": "full prompt string",
            "variation": {...}
        }
    """
    variations = extracted_scene.get("variations", [])

    # Get the specific variation (wrap around if index exceeds available)
    if variations:
        variation = variations[variation_index % len(variations)]
    else:
        variation = {"angle": "overhead", "focus": "centered", "depth": "sharp focus"}

    # Build the prompt with extracted scene elements + variation
    prompt_parts = [
        # Subject first (Flux 2 best practice)
        f"{item_name} with {item_description}",
        # Realism descriptors
        extracted_scene.get("realism", "authentic food texture, natural imperfections"),
        # Scene elements
        extracted_scene.get("background", ""),
        extracted_scene.get("lighting", ""),
        extracted_scene.get("mood", ""),
        extracted_scene.get("props", ""),
        # Variation elements
        variation.get("angle", ""),
        variation.get("focus", ""),
        variation.get("depth", ""),
        # Photography quality
        "editorial food photography, shot on Canon 5D Mark IV, high resolution, appetizing presentation",
    ]

    # Filter empty parts and join
    full_prompt = ", ".join(part for part in prompt_parts if part)

    return {
        "prompt": full_prompt,
        "scene_name": extracted_scene.get("name", "Custom Style"),
        "variation_index": variation_index,
        "variation": variation,
    }
