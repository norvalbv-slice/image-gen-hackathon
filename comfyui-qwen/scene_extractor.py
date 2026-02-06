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


EXTRACTION_PROMPT = """You are an expert food photography analyst. Analyze this food photograph and extract EXACT scene details for recreating this SPECIFIC style with DIFFERENT foods.

CRITICAL: Describe the SCENE (background, surface, lighting, props) in FOOD-AGNOSTIC terms.
- Do NOT mention the specific food type in scene descriptions
- Use generic terms: "serving board" not "pizza board", "serving utensil" not "pizza server"
- The scene should work for ANY food (pasta, salad, burger, etc.)

Extract the following details:

1. **name**: Short descriptive name for this photography style (no food names)
   Example: "Rustic Farmhouse Side-Lit" not "Rustic Pizza Shot"

2. **background**: EXACT surface description (NO food references):
   - Material type (wood grain direction, marble pattern, concrete texture)
   - Exact color (whitewashed, weathered gray, dark espresso, light oak)
   - Condition (distressed, polished, rough, smooth)
   Example: "whitewashed weathered wood planks with visible gray grain, slightly distressed finish"

3. **surface_object**: What the food sits ON (generic terms):
   - Use: "round wooden serving board", "ceramic plate", "slate board"
   - NOT: "pizza board", "pasta bowl" - keep it generic
   Example: "round rustic wooden serving board with dark brown finish and short handle"

4. **props**: Visible items EXCLUDING the food itself (generic utensil names):
   - Use: "metal serving spatula", "wooden spoon", "cloth napkin"
   - NOT: "pizza cutter", "pasta fork"
   - Include positions: "on left side", "in background"
   Example: "metal serving spatula on left side, scattered fresh herb leaves, light flour dusting on board"

5. **lighting**: Exact lighting setup:
   - Direction, color temperature, shadow characteristics
   - Do NOT reference the food (no "highlights on cheese")
   Example: "strong side lighting from upper left, neutral-cool daylight, medium shadows falling right"

6. **camera_angle**: Camera position:
   - Angle in degrees (overhead 90°, 45°, 30°, eye-level 0°)
   - Distance (close-up, medium, full scene)
   Example: "approximately 30-degree angle from front-left corner, medium distance"

7. **depth_of_field**: Focus characteristics:
   - Describe without food references
   Example: "sharp focus on center subject, slight blur on edges, soft bokeh on background"

8. **color_palette**: Scene colors only (exclude food colors):
   - Background and prop colors
   Example: "warm browns, cream whites, weathered grays, green herb accents"

9. **mood**: Overall atmosphere:
   Example: "rustic farmhouse, casual inviting, artisanal"

10. **detected_food_type**: What food IS in this image?
    - pizza, pasta, salad, burger, sandwich, dessert, soup, etc.

Return as valid JSON:
{
  "name": "Style Name (no food type)",
  "background": "exact background (food-agnostic)",
  "surface_object": "serving surface (generic)",
  "props": "items and positions (generic utensils)",
  "lighting": "lighting setup (no food refs)",
  "camera_angle": "angle and distance",
  "depth_of_field": "focus characteristics",
  "color_palette": "scene colors only",
  "mood": "atmosphere",
  "detected_food_type": "the actual food in image"
}

REMEMBER: The scene description must work for ANY food type, not just the one shown."""


def detect_image_mime_type(image_base64: str) -> str:
    """Detect MIME type from base64 image data."""
    import base64

    try:
        # Decode first few bytes to check magic numbers
        data = base64.b64decode(image_base64[:100])
        if data[:4] == b"\x89PNG":
            return "image/png"
        elif data[:2] == b"\xff\xd8":
            return "image/jpeg"
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        elif data[:3] == b"GIF":
            return "image/gif"
    except:
        pass
    # Default to jpeg which is widely supported
    return "image/jpeg"


def extract_scene_openai(image_base64: str, api_key: Optional[str] = None) -> Dict:
    """Use GPT-4V to extract scene from reference image."""
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    # Detect actual image format
    mime_type = detect_image_mime_type(image_base64)
    print(f"[SCENE EXTRACTOR] Detected image MIME type: {mime_type}")

    content = [
        {"type": "text", "text": EXTRACTION_PROMPT},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{image_base64}",
                "detail": "high",
            },
        },
    ]

    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[{"role": "user", "content": content}],
        max_completion_tokens=2500,
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
    apply_angle_variations: bool = True,
    **kwargs,
) -> Dict:
    """Build a generation prompt using extracted scene config with universal hierarchy.

    Uses the same hierarchy as the main handler to prevent style bleed:
    1. Camera directive (highest emphasis)
    2. Food anchor (item_name as primary subject)
    3. Description + universal distribution
    4. Scene elements (isolated from food identity)
    5. Orientation + quality
    """
    # Standard angle variations for multi-image generation
    standard_variations = [
        {
            "label": "Overhead",
            "angle": "CAMERA DIRECTLY ABOVE looking straight down, perfect overhead bird's eye view",
            "focus": "entire dish centered in frame",
            "depth": "sharp focus throughout all elements",
        },
        {
            "label": "45° Angle",
            "angle": "CAMERA AT 45 DEGREES looking down at dish from corner angle",
            "focus": "front edge sharp with depth receding",
            "depth": "shallow depth of field with soft bokeh background",
        },
        {
            "label": "Eye Level",
            "angle": "CAMERA AT EYE LEVEL shooting horizontally across the dish",
            "focus": "dramatic side profile view",
            "depth": "shallow focus on nearest edge with background blur",
        },
        {
            "label": "Close-up",
            "angle": "EXTREME CLOSE-UP MACRO filling frame with texture detail",
            "focus": "texture and ingredient detail dominating frame",
            "depth": "extremely shallow depth with tiny focal plane",
        },
    ]

    if apply_angle_variations:
        variation = standard_variations[variation_index % len(standard_variations)]
        camera_angle = variation["angle"]
        depth_of_field = variation["depth"]
    else:
        variation = {
            "label": "Reference",
            "angle": "from reference",
            "focus": "from reference",
            "depth": "from reference",
        }
        camera_angle = extracted_scene.get("camera_angle", "")
        depth_of_field = extracted_scene.get("depth_of_field", "")

    # Scene details extracted as food-agnostic by GPT/Claude
    surface = extracted_scene.get("surface_object", "")
    props = extracted_scene.get("props", "")
    background = extracted_scene.get("background", "")
    lighting = extracted_scene.get("lighting", "")
    mood = extracted_scene.get("mood", "")
    color_palette = extracted_scene.get("color_palette", "")

    # Universal prompt hierarchy (same structure as handler's build_scene_prompt)
    prompt_parts = [
        # 1. Camera directive (triple emphasis = highest priority for Qwen)
        f"((({camera_angle})))" if camera_angle else "",
        f"(({depth_of_field}))" if depth_of_field else "",
        # 2. Food anchor - item_name IS the anchor (prevents style bleed)
        "professional food photography",
        f"(({item_name}))",
        # 3. Description de-emphasized so dish name drives the visual, ingredients refine
        f"[{item_description}]",
        "each ingredient prepared and cut in the form appropriate for this specific dish as a professional chef would serve it, ingredients arranged and distributed naturally across the dish, evenly balanced and overlapping organically, not placed in separate literal piles or clusters, no whole uncut pieces unless that is how the dish is traditionally served",
        # 4. Scene elements (style isolated from food identity)
        f"on {surface}" if surface else "",
        background,
        props,
        lighting,
        f"color palette: {color_palette}" if color_palette else "",
        mood,
        # 5. Orientation + realism + quality
        "dish right-side up on table with correct gravity and natural orientation",
        "authentic food texture with natural imperfections, real ingredients not CGI or plastic, matte surfaces with organic color variations",
        "professional editorial food photography, high resolution, appetizing presentation",
    ]

    full_prompt = ", ".join(part for part in prompt_parts if part and part.strip())

    return {
        "prompt": full_prompt,
        "scene_name": extracted_scene.get("name", "Custom Style"),
        "variation_index": variation_index,
        "variation": variation,
        "camera_angle": camera_angle,
        "extracted_scene": extracted_scene,
    }
