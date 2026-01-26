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


def get_food_realism(food_type: str) -> str:
    """
    Get food-type-specific realism descriptors.
    This ensures pasta looks like pasta, not pizza with pasta on top!
    """
    realism_by_type = {
        "pizza": "authentic handmade pizza appearance with natural irregularities, slightly uneven cheese melt, charred crust spots, real food texture not CGI or plastic, matte finish on ingredients, organic imperfections",
        "pasta": "authentic Italian pasta texture, al dente appearance, creamy sauce coating each strand naturally, real parmesan shavings, genuine steam rising, matte food textures not plastic, organic imperfections in sauce distribution",
        "salad": "fresh crisp vegetables with natural water droplets, authentic leaf textures with natural imperfections, real dressing pooling naturally, organic colors, matte vegetable surfaces not waxy or plastic",
        "burger": "authentic grilled patty with natural char marks, real melted cheese dripping naturally, fresh crisp lettuce with natural edges, genuine sesame seed bun texture, juicy appearance with natural imperfections",
        "sandwich": "authentic fresh bread texture with natural crumb structure, real layered fillings visible, genuine spread application, natural ingredient colors, matte surfaces not plastic or CGI",
        "dessert": "authentic pastry textures with natural imperfections, real cream with organic swirls, genuine fruit with natural blemishes, authentic powdered sugar dusting, not plastic or artificially perfect",
        "soup": "authentic steaming liquid with natural surface texture, real ingredient pieces floating naturally, genuine broth with organic color variations, natural steam rising, not CGI or plastic looking",
        "appetizer": "authentic artisan preparation with natural imperfections, real garnish placement with organic arrangement, genuine sauce drizzles with natural pooling, matte food textures",
    }

    # Default realism for unknown food types
    default_realism = "authentic food texture with natural imperfections, real ingredients not CGI or plastic, matte surfaces with organic color variations, genuine homemade appearance"

    return realism_by_type.get(food_type.lower(), default_realism)


def build_prompt_from_extracted_scene(
    item_name: str,
    item_description: str,
    extracted_scene: Dict,
    variation_index: int = 0,
    target_food_type: str = None,
    apply_angle_variations: bool = True,
) -> Dict:
    """
    Build a DETAILED generation prompt using extracted scene config.

    Args:
        item_name: Name of the food item to generate
        item_description: Description/ingredients
        extracted_scene: Scene config from extract_scene_from_image()
        variation_index: Which variation to use (0-3)
        target_food_type: Type of food being generated (pizza, pasta, etc.)

    Returns:
        {
            "prompt": "full prompt string",
            "variation": {...}
        }
    """
    # Detect target food type if not provided
    if not target_food_type:
        item_lower = item_name.lower()
        if "pizza" in item_lower or "flatbread" in item_lower:
            target_food_type = "pizza"
        elif (
            "pasta" in item_lower
            or "spaghetti" in item_lower
            or "penne" in item_lower
            or "carbonara" in item_lower
            or "lasagna" in item_lower
        ):
            target_food_type = "pasta"
        elif "salad" in item_lower:
            target_food_type = "salad"
        elif "burger" in item_lower:
            target_food_type = "burger"
        elif "sandwich" in item_lower or "sub" in item_lower or "wrap" in item_lower:
            target_food_type = "sandwich"
        elif (
            "cake" in item_lower
            or "pie" in item_lower
            or "dessert" in item_lower
            or "tiramisu" in item_lower
        ):
            target_food_type = "dessert"
        elif "soup" in item_lower or "stew" in item_lower:
            target_food_type = "soup"
        else:
            target_food_type = "appetizer"  # Generic fallback

    # Get food-appropriate realism (pasta shouldn't have "charred crust" etc.)
    food_realism = get_food_realism(target_food_type)

    # Adapt food_state if generating different food type than reference
    ref_food_type = extracted_scene.get("detected_food_type", "pizza")
    food_state = extracted_scene.get("food_state", "")

    # Don't use pizza-specific food_state for non-pizza items
    if target_food_type != "pizza" and ref_food_type == "pizza":
        food_state = ""  # Clear pizza-specific states like "slice lifted"

    # Apply VARIATIONS for multiple images (different angles/compositions)
    # Only apply for text2img (different food type) - img2img preserves reference composition
    # Using directive camera language for better model understanding
    standard_variations = [
        {
            "angle": "CAMERA DIRECTLY ABOVE looking straight down, perfect overhead bird's eye view",
            "focus": "entire dish centered in frame",
            "depth": "sharp focus throughout all elements",
        },
        {
            "angle": "CAMERA AT 45 DEGREES looking down at dish from corner angle",
            "focus": "front edge sharp with depth receding",
            "depth": "shallow depth of field with soft bokeh background",
        },
        {
            "angle": "CAMERA AT EYE LEVEL shooting horizontally across the dish",
            "focus": "dramatic side profile view",
            "depth": "shallow focus on nearest edge with background blur",
        },
        {
            "angle": "EXTREME CLOSE-UP MACRO filling frame with texture detail",
            "focus": "texture and ingredient detail dominating frame",
            "depth": "extremely shallow depth with tiny focal plane",
        },
    ]

    if apply_angle_variations:
        # text2img mode: Apply different angles for each image
        variation = standard_variations[variation_index % len(standard_variations)]
        camera_angle = variation["angle"]
        depth_of_field = variation["depth"]
    else:
        # img2img mode: Use extracted scene's angle (preserve reference composition)
        variation = {
            "angle": "from reference",
            "focus": "from reference",
            "depth": "from reference",
        }
        camera_angle = extracted_scene.get("camera_angle", "")
        depth_of_field = extracted_scene.get("depth_of_field", "")

    # Scene details are now extracted as food-agnostic by GPT-5.1
    # No brittle string replacements needed - the LLM does the smart work
    surface = extracted_scene.get("surface_object", "rustic wooden serving board")
    props = extracted_scene.get("props", "")
    background = extracted_scene.get("background", "")
    lighting = extracted_scene.get("lighting", "")
    mood = extracted_scene.get("mood", "")
    color_palette = extracted_scene.get("color_palette", "")

    # Food-context prefix to bias model interpretation toward food photography
    food_context = "professional food photography, food dish only, close-up of plated food"

    prompt_parts = [
        # Camera angle FIRST with emphasis markers for Qwen attention
        # Triple parens = highest priority, double = high, single = medium
        f"((({camera_angle})))" if camera_angle else "",
        f"(({depth_of_field}))" if depth_of_field else "",
        # Food context
        food_context,
        # Subject
        f"{item_name} with {item_description}",
        # Food state (only if same food type)
        food_state,
        # Surface/serving object (food-agnostic from GPT-5.1)
        f"on {surface}" if surface else "",
        # Background
        background,
        # Props (food-agnostic)
        props,
        # Lighting setup
        lighting,
        # Color palette
        f"((color palette: {color_palette}))" if color_palette else "",
        # Mood/atmosphere
        mood,
        # Food-specific realism details
        food_realism,
        # Photography quality
        "professional editorial food photography, high resolution, appetizing presentation",
    ]

    # Filter empty parts and join
    full_prompt = ", ".join(part for part in prompt_parts if part and part.strip())

    return {
        "prompt": full_prompt,
        "scene_name": extracted_scene.get("name", "Custom Style"),
        "variation_index": variation_index,
        "variation": variation,  # Include variation details
        "camera_angle": camera_angle,  # Use variation angle, not extracted
        "extracted_scene": extracted_scene,
        "target_food_type": target_food_type,
        "food_realism": food_realism,
    }
