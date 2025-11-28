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


EXTRACTION_PROMPT = """You are an expert food photography analyst. Analyze this food photograph and extract EXACT details for recreating this SPECIFIC style in new images.

BE EXTREMELY SPECIFIC - we need to replicate this exact look, not a generic interpretation.

Extract the following details:

1. **name**: Short descriptive name for this specific style

2. **background**: EXACT surface description including:
   - Material type (wood grain direction, marble pattern, concrete texture)
   - Exact color (whitewashed, weathered gray, dark espresso, light oak)
   - Condition (distressed, polished, rough, smooth)
   - Any visible backdrop behind the surface
   Example: "whitewashed weathered wood planks with visible gray grain, slightly distressed finish"

3. **surface_object**: What is the food placed ON?
   - Serving board, plate, slate, paper, directly on table?
   - Material and color of this object
   Example: "round rustic wooden serving board with dark brown finish and metal handle"

4. **props**: ALL visible items in the frame:
   - Utensils (spatula, fork, knife, pizza cutter)
   - Garnishes (loose herbs, scattered ingredients)
   - Napkins, towels, bottles
   - Position of each item (left side, background, etc.)
   Example: "wooden pizza spatula/server on left side, scattered fresh oregano leaves"

5. **food_state**: Specific state of the food:
   - Is there a slice cut out? How many?
   - Is there a cheese pull or lift happening?
   - Steam visible?
   - Any toppings falling off edge?
   Example: "one triangular slice lifted showing cheese stretch, remaining pizza intact"

6. **lighting**: Exact lighting setup:
   - Direction (from left, right, above, behind)
   - Color temperature (warm golden, cool white, neutral)
   - Shadow intensity and direction
   - Any highlights or rim lighting
   Example: "dramatic side lighting from left, warm golden tone, deep shadows on right, highlight on crust edge"

7. **camera_angle**: Exact camera position:
   - Angle in degrees (overhead 90°, 45°, 30°, eye-level 0°)
   - Perspective (straight-on, from corner, from side)
   - Distance (close-up, medium, full scene)
   Example: "approximately 30-degree angle from front-left corner, medium distance showing full pizza plus props"

8. **depth_of_field**: Focus characteristics:
   - What's in sharp focus?
   - What's blurred?
   - Bokeh quality in background
   Example: "sharp focus on front half of pizza, slight blur on back edge, soft bokeh on background"

9. **color_palette**: Dominant colors in the scene:
   - List 3-5 main colors
   Example: "warm browns, cream whites, red sauce tones, green herb accents"

Return your analysis as valid JSON:
{
  "name": "Style Name",
  "background": "exact background description",
  "surface_object": "what food sits on",
  "props": "all visible items with positions",
  "food_state": "slice cut, cheese pull, etc.",
  "lighting": "exact lighting setup",
  "camera_angle": "exact angle and perspective",
  "depth_of_field": "focus characteristics",
  "color_palette": "dominant colors",
  "mood": "overall atmosphere",
  "realism": "texture and authenticity details"
}

BE SPECIFIC - generic descriptions like "wooden table" are not useful. We need "whitewashed weathered pine planks" level of detail."""


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
    Build a DETAILED generation prompt using extracted scene config.

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
    # Build comprehensive prompt with ALL extracted details
    prompt_parts = [
        # Subject first (Flux 2 best practice)
        f"{item_name} with {item_description}",
        
        # Food state (slice cut, cheese pull, etc.) - IMPORTANT for matching reference
        extracted_scene.get("food_state", ""),
        
        # Surface/serving object
        f"on {extracted_scene.get('surface_object', 'rustic wooden board')}" if extracted_scene.get("surface_object") else "",
        
        # Background - exact description
        extracted_scene.get("background", ""),
        
        # Props with positions - makes scene match
        extracted_scene.get("props", ""),
        
        # Lighting setup - critical for matching style
        extracted_scene.get("lighting", ""),
        
        # Camera angle and perspective
        extracted_scene.get("camera_angle", ""),
        
        # Depth of field
        extracted_scene.get("depth_of_field", ""),
        
        # Color palette influence
        f"color palette of {extracted_scene.get('color_palette', '')}" if extracted_scene.get("color_palette") else "",
        
        # Mood/atmosphere
        extracted_scene.get("mood", ""),
        
        # Realism/texture details
        extracted_scene.get("realism", "authentic food texture, natural imperfections"),
        
        # Photography quality
        "professional editorial food photography, high resolution, appetizing presentation",
    ]

    # Filter empty parts and join
    full_prompt = ", ".join(part for part in prompt_parts if part and part.strip())

    return {
        "prompt": full_prompt,
        "scene_name": extracted_scene.get("name", "Custom Style"),
        "variation_index": variation_index,
        "camera_angle": extracted_scene.get("camera_angle", ""),
        "extracted_scene": extracted_scene,
    }
