# AI Menu Image Generation - ComfyUI + Flux 2.0 on RunPod

> **Winter Hackathon 2025** - Single-click automation to give shops a menu full of great-looking AI-generated images.

## Architecture

**ONE endpoint, TWO modes** - the handler automatically picks the right workflow based on your request.

```
┌─────────────────────────────────────────────────────────────────┐
│                     OWNERS PORTAL (Separate Repo)               │
│  - Selects menu items                                           │
│  - Chooses scene/style OR uploads reference image               │
│  - Displays generated images                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS POST (JSON)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RUNPOD SERVERLESS ENDPOINT                    │
│  Endpoint ID: hbvg2b5ucr59mx                                    │
│  Image: benjithegreat/comfyui-flux2:fp8-v24                     │
│  GPU: NVIDIA A100 80GB                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MODE 1: Scene-Based (scene: "rustic_italian")                  │
│  ├── Uses pre-defined scene from scenes.json                    │
│  ├── Text-to-image workflow (random noise → image)              │
│  └── 4 variations per scene (overhead, 45°, eye-level, macro)   │
│                                                                 │
│  MODE 2: Reference Image (reference_image: "base64...")         │
│  ├── GPT-5.1 analyzes photo → extracts scene config             │
│  ├── Img2img workflow (reference latent → similar image)        │
│  └── Preserves ~40% of reference style (denoise: 0.6)           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
comfyui/
├── handler_slim.py       # Main serverless handler (picks workflow automatically)
├── workflow.json         # Text-to-image (for scene-based mode)
├── workflow_img2img.json # Img2img (for reference image mode)
├── scenes.json           # 6 pre-defined scenes with 4 variations each
├── templates.json        # Food category prompt templates
├── scene_extractor.py    # GPT-5.1 reference image analysis
├── Dockerfile.slim       # Slim Docker (~2GB, models download at runtime)
├── test_fp8_endpoint.sh  # Test scene-based generation
└── test_reference.sh     # Test reference image mode
```

## Quick Start

```bash
cd comfyui

# Set your API keys
export RUNPOD_API_KEY=your_runpod_key
export OPENAI_API_KEY=your_openai_key  # Only needed for reference image mode
```

## Why Docker Slim

We use a **slim Docker image** (~2GB) instead of bundling the 54GB models:

| Approach | Image Size | Cold Start | Subsequent Runs |
|----------|------------|------------|-----------------|
| Fat image (models baked in) | ~56GB | 5-10 min (pull) | Fast |
| **Slim image (our approach)** | ~2GB | 5-10 min (download models) | Fast (FlashBoot cached) |

**Benefits:**
- Much faster Docker push/pull cycles during development
- RunPod's FlashBoot caches the downloaded models
- Easy to update code without re-uploading 54GB
- Models downloaded from Hugging Face (fast CDN)

### Mode 1: Scene-Based Generation

Use pre-defined scenes (no OpenAI key required):

```bash
# Generate 4 pizza images with rustic Italian theme
./test_fp8_endpoint.sh rustic_italian 4

# Try other scenes
./test_fp8_endpoint.sh modern_minimal 4
./test_fp8_endpoint.sh premium_upscale 4
```

**Available Scenes:** (work with ANY food type - pizza, pasta, salads, desserts, etc.)

| Scene | Description | Best For |
|-------|-------------|----------|
| `rustic_italian` | Warm wood, traditional | Classic Italian restaurants |
| `modern_minimal` | White marble, clean, Instagram-worthy | Modern cafes |
| `cozy_homestyle` | Checkered tablecloth, family-style | Family restaurants |
| `premium_upscale` | Dark slate, dramatic lighting | Fine dining |
| `street_food` | Urban, energetic, food truck vibes | Casual/fast-casual |
| `garden_fresh` | Natural light, organic, farm-to-table | Health-focused |
| `industrial_craft` | Concrete, urban workshop aesthetic | Artisan/craft shops |

Each scene generates **4 variations** with different angles:
- `0` - Overhead flat lay
- `1` - 45-degree angle
- `2` - Close-up detail
- `3` - Side/profile view

### Mode 2: Reference Image (Match Existing Style)

Upload an existing menu photo → GPT-5.1 extracts the style → new images match it:

```bash
# Use your shop's existing photo as style reference
./test_reference.sh path/to/your_photo.jpg 4
```

**How it works:**
1. Shop uploads their best existing photo
2. GPT-5.1 extracts: background, lighting, props, composition, etc.
3. Flux 2.0 generates new images matching that exact style
4. Optionally save as custom scene for reuse

## API Usage

### Scene-Based Request

```bash
curl -X POST "https://api.runpod.ai/v2/hbvg2b5ucr59mx/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "pepperoni pizza",
      "item_description": "pepperoni, mozzarella, fresh basil",
      "scene": "rustic_italian",
      "num_images": 4
    }
  }'
```

### Progressive Loading (Single Image with Specific Angle)

For better UX, request images one at a time with `variation_index`:

```bash
# Request specific angle (0=overhead, 1=45°, 2=closeup, 3=side)
curl -X POST "https://api.runpod.ai/v2/hbvg2b5ucr59mx/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "onion rings",
      "item_description": "crispy golden fried",
      "scene": "street_food",
      "num_images": 1,
      "variation_index": 0
    }
  }'
```

| `variation_index` | Angle |
|-------------------|-------|
| 0 | overhead flat lay |
| 1 | 45-degree hero angle |
| 2 | close-up detail |
| 3 | side/profile view |

**Frontend can make 4 parallel requests** with `variation_index: 0, 1, 2, 3` - each returns in ~20s instead of waiting ~80s for all 4.

### Reference Image Request

```bash
curl -X POST "https://api.runpod.ai/v2/hbvg2b5ucr59mx/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "garlic bread",
      "item_description": "buttery with herbs",
      "reference_image": "'"$(base64 -i your_photo.jpg | tr -d '\n')"'",
      "extract_scene": true,
      "openai_api_key": "'"$OPENAI_API_KEY"'",
      "denoise": 0.6,
      "num_images": 4
    }
  }'
```

### Response Format

```json
{
  "status": "COMPLETED",
  "output": {
    "status": "success",
    "scene": "rustic_italian",
    "scene_name": "Rustic Italian",
    "num_images": 1,
    "images": [
      {
        "image_base64": "iVBORw0KGgo...",
        "seed": 1234567890,
        "variation": {
          "angle": "overhead flat lay shot",
          "focus": "entire dish centered",
          "depth": "sharp focus throughout"
        },
        "variation_index": 0,
        "prompt": "onion rings with crispy golden fried, ..."
      }
    ],
    "available_scenes": ["rustic_italian", "modern_minimal", "cozy_homestyle", "premium_upscale", "street_food", "garden_fresh", "industrial_craft"]
  }
}
```

## Denoise Parameter (Reference Mode)

Controls how much of the reference image is preserved:

| Value | Effect |
|-------|--------|
| `0.3` | Very similar to reference (70% preserved) |
| `0.5` | Balanced blend |
| **`0.6`** | **Default** - good for different food items |
| `0.8` | Mostly new generation |

## Docker & Deployment

We use a **slim Docker image** (~2GB) - models download on first run:

```bash
# Build (IMPORTANT: use --platform for RunPod compatibility)
cd comfyui && docker buildx build --platform linux/amd64 -f Dockerfile.slim -t benjithegreat/comfyui-flux2:fp8-v24 --push .

# Update RunPod template (via MCP or dashboard)
```

**Current deployment:**
- Endpoint ID: `hbvg2b5ucr59mx`
- Template ID: `07hps30fle`
- Docker Image: `benjithegreat/comfyui-flux2:fp8-v24`

## Important Notes

### Cold Starts
- **First request:** 5-10 min (downloading 54GB of models)
- **Subsequent:** ~25 seconds per image
- RunPod FlashBoot caches models for fast warm starts

### Costs
- A100 80GB: ~$1.40/hour
- Workers auto-scale down after 10 seconds idle
- Keep `workersMin: 0` to avoid idle costs

### Dev Mode (Live Prompt Editing)

1. **Create your own branch** with modified `scenes.json` or `templates.json`
2. **Get the raw GitHub URL** for your file
3. **Pass the URL to the API** - configs load from your branch

### Example: Testing Your Own Scenes

```bash
export SCENES_URL="https://raw.githubusercontent.com/your-branch/comfyui/scenes.json"
./test_fp8_endpoint.sh rustic_italian 4
```

Or: 

# 1. Create a branch and edit scenes.json
git checkout -b my-experiment
# Edit comfyui/scenes.json
git add . && git commit -m "test: my scene changes"
git push origin my-experiment

# 2. Get the raw URL (replace with your actual branch)
# https://raw.githubusercontent.com/norvalbv-slice/image-gen-hackathon/my-experiment/comfyui/scenes.json

# 3. Test with your custom scenes
export SCENES_URL="https://raw.githubusercontent.com/norvalbv-slice/image-gen-hackathon/my-experiment/comfyui/scenes.json"
./test_fp8_endpoint.sh rustic_italian 4

# The endpoint will fetch your scenes.json instead of the baked-in one

```json
curl -X POST "https://api.runpod.ai/v2/hbvg2b5ucr59mx/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "pepperoni pizza",
      "scenes_url": "https://raw.githubusercontent.com/YOUR_BRANCH/comfyui/scenes.json",
      "item_description": "pepperoni, mozzarella, fresh basil",
      "num_images": 4
    }
  }'
```

## Related Resources

- **Epic:** [sc-640877](https://app.shortcut.com/slicernd/epic/640877)
- **Slack:** `#proj-temp-ai-image-gen`
- **ComfyUI Docs:** https://docs.comfy.org
- **Flux 2.0 Model:** https://huggingface.co/black-forest-labs/FLUX.2-dev

