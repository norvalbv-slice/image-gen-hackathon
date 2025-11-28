# AI Menu Image Generation - ComfyUI + Flux 2.0 on RunPod

> **Winter Hackathon 2025** - Single-click automation to give pizza shops a menu full of great-looking AI-generated images.

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
│  Image: benjithegreat/comfyui-flux2:fp8-v13                     │
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
├── llm_judge.py          # GPT-5.1-mini/Claude for auto-selecting best image
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

**Available Scenes:**

| Scene | Description | Best For |
|-------|-------------|----------|
| `rustic_italian` | Warm wood, brick oven, traditional | Classic pizzerias |
| `modern_minimal` | White marble, clean, Instagram-worthy | Modern cafes |
| `cozy_homestyle` | Checkered tablecloth, family-style | Family restaurants |
| `premium_upscale` | Dark slate, dramatic lighting | Fine dining |
| `street_food` | Urban, energetic, food truck vibes | Casual/fast-casual |
| `garden_fresh` | Natural light, organic, farm-to-table | Health-focused |

Each scene generates **4 variations** with different angles:
- Overhead flat lay
- 45-degree angle
- Eye-level shot
- Macro close-up

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
    "mode": "reference_img2img",
    "scene_name": "Rustic Pizzeria Style",
    "num_images": 4,
    "denoise": 0.6,
    "extracted_scene": {
      "name": "Rustic Pizzeria Style",
      "background": "whitewashed weathered wood planks",
      "surface_object": "round rustic wooden serving board",
      "props": "wooden pizza spatula on left side",
      "lighting": "dramatic side lighting from left",
      "camera_angle": "30-degree angle from front-left"
    },
    "images": [
      {
        "image_base64": "iVBORw0KGgo...",
        "seed": 1234567890,
        "prompt": "garlic bread with buttery herbs, ..."
      }
    ]
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
# Build
cd comfyui && docker build -f Dockerfile.slim -t benjithegreat/comfyui-flux2:fp8-v13 .

# Push
docker push benjithegreat/comfyui-flux2:fp8-v13

# Update RunPod template (via MCP or dashboard)
```

**Current deployment:**
- Endpoint ID: `hbvg2b5ucr59mx`
- Template ID: `07hps30fle`
- Docker Image: `benjithegreat/comfyui-flux2:fp8-v13`

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

## LLM as Judge

When `auto_select: true`, we send all generated images to GPT-4V/Claude to pick the best one:

```python
# In handler_slim.py
if auto_select and num_images > 1:
    judge_result = judge_images(images_b64, item_name)
    # Returns: { best_index: 2, reasoning: "..." }
```

**How it works:**
1. All 4 variations sent to vision LLM
2. LLM evaluates: appetizing appeal, realism, composition, lighting
3. Returns best image index with reasoning

**Cost:** ~$0.01-0.05 per evaluation

**For hackathon demo:** Better to show all 4 and let owner choose (more impressive UX).

## Related Resources

- **Epic:** [sc-640877](https://app.shortcut.com/slicernd/epic/640877)
- **Slack:** `#proj-temp-ai-image-gen`
- **ComfyUI Docs:** https://docs.comfy.org
- **Flux 2.0 Model:** https://huggingface.co/black-forest-labs/FLUX.2-dev

