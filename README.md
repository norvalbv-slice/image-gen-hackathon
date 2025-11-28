# AI Menu Image Generation - ComfyUI + Flux 2.0 on RunPod

> **Winter Hackathon 2025** - Single-click automation to give pizza shops a menu full of great-looking AI-generated images.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OWNERS PORTAL (Separate Repo)               │
│  - Selects menu items                                           │
│  - Chooses scene/style                                          │
│  - Displays generated images                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS POST (JSON)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RUNPOD SERVERLESS ENDPOINT                    │
│  Endpoint ID: mjiwr7uipx2nbs                                    │
│  Image: benjithegreat/comfyui-flux2:fp8-v7                      │
│  GPU: NVIDIA A100 80GB                                          │
│                                                                 │
│  ComfyUI + Flux 2.0 FP8 → Returns base64 PNG images            │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 File Structure

```
comfyui/
├── handler_slim.py      # Main RunPod serverless handler
├── workflow.json        # ComfyUI node graph for Flux 2.0
├── scenes.json          # Scene configurations (6 themes, 4 variations each)
├── templates.json       # Food category prompt templates
├── llm_judge.py         # GPT-4V/Claude image evaluation
├── Dockerfile.slim      # Slim Docker image (~2GB, models downloaded at runtime)
├── build.sh             # Build Docker image
├── push.sh              # Push to Docker Hub
└── test_fp8_endpoint.sh # CLI to test the endpoint
```

## 🚀 Quick Start - Testing the Endpoint

```bash
cd comfyui

# Set your RunPod API key
export RUNPOD_API_KEY=your_key_here

# Generate 4 pizza images with rustic Italian theme
./test_fp8_endpoint.sh rustic_italian 4

# Try different scenes
./test_fp8_endpoint.sh modern_minimal 4
./test_fp8_endpoint.sh premium_upscale 4
./test_fp8_endpoint.sh street_food 4
./test_fp8_endpoint.sh garden_fresh 4
./test_fp8_endpoint.sh cozy_homestyle 4
```

### Available Scenes

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

## 🐳 Why Docker Slim?

We use a **slim Docker image** (~2GB) instead of bundling the 54GB models:

| Approach | Image Size | Cold Start | Subsequent Runs |
|----------|------------|------------|-----------------|
| Fat image (models baked in) | ~56GB | 5-10 min (pull) | Fast |
| **Slim image (our approach)** | ~2GB | 5-10 min (download models) | Fast (FlashBoot cached) |

**Benefits:**
- ✅ Much faster Docker push/pull cycles during development
- ✅ RunPod's FlashBoot caches the downloaded models
- ✅ Easy to update code without re-uploading 54GB
- ✅ Models downloaded from Hugging Face (fast CDN)

## 🔄 Development & Deployment Flow

### Making Changes

```bash
# 1. Edit the code
vim comfyui/handler_slim.py   # Main logic
vim comfyui/scenes.json       # Scene configurations
vim comfyui/workflow.json     # ComfyUI node graph

# 2. Build new Docker image
cd comfyui
./build.sh   # Creates benjithegreat/comfyui-flux2:fp8-v7

# 3. Push to Docker Hub
./push.sh    # Pushes to Docker Hub

# 4. Update RunPod template (if changing image tag)
# Go to RunPod dashboard → Templates → Update image tag
# OR use RunPod MCP: mcp_runpod_update-template

# 5. Test
./test_fp8_endpoint.sh rustic_italian 4
```

### Forcing New Workers

RunPod caches workers with FlashBoot. To force new code:

1. **Change the Docker tag** (e.g., `fp8-v7` → `fp8-v8`)
2. Update the RunPod template to use the new tag
3. Old workers will be replaced on next request

### Current Deployment

- **Endpoint ID:** `mjiwr7uipx2nbs`
- **Template ID:** `07hps30fle`
- **Docker Image:** `benjithegreat/comfyui-flux2:fp8-v7`
- **GPU:** A100 80GB only (forced for consistent ~25s generation)

## 🤖 LLM as Judge

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

## 📡 API Reference

### Submit Generation Job

```bash
curl -X POST "https://api.runpod.ai/v2/mjiwr7uipx2nbs/run" \
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
# Returns: { "id": "job-id", "status": "IN_QUEUE" }
```

### Poll for Status

```bash
curl "https://api.runpod.ai/v2/mjiwr7uipx2nbs/status/{job_id}" \
  -H "Authorization: Bearer $RUNPOD_API_KEY"
```

### Response Format

```json
{
  "status": "COMPLETED",
  "output": {
    "status": "success",
    "scene_id": "rustic_italian",
    "scene_name": "Rustic Italian Pizzeria",
    "num_images": 4,
    "images": [
      {
        "image_base64": "iVBORw0KGgo...",
        "seed": 1234567890,
        "variation": {
          "angle": "overhead flat lay",
          "focus": "sharp focus on toppings",
          "depth": "shallow depth of field"
        },
        "prompt": "pepperoni pizza with pepperoni, mozzarella..."
      }
    ]
  }
}
```

## ⚠️ Important Notes

### Cold Starts
- **First request after idle:** 5-10 minutes (downloading 54GB of models)
- **Subsequent requests:** ~25 seconds per image
- RunPod FlashBoot caches models, so warm workers are fast

### Costs
- **A100 80GB:** ~$1.40/hour
- **Workers auto-scale down** after 10 seconds idle
- **Tip:** Keep `workersMin: 0` to avoid idle costs

### Models Used
- **UNET:** `flux2_dev_fp8mixed.safetensors` (~17GB)
- **Text Encoder:** `mistral_3_small_flux2_fp8.safetensors` (~18GB)
- **VAE:** `flux2-vae.safetensors` (~168MB)

## 👥 Team

- **Rick Monro** - Product lead
- **Daniele Baelde** - Technical lead, Owners Portal
- **David Robinson** - Engineering
- **Benji Norval** - RunPod/ComfyUI backend

## 📚 Related Resources

- **Epic:** [sc-640877](https://app.shortcut.com/slicernd/epic/640877)
- **Slack:** `#proj-temp-ai-image-gen`
- **ComfyUI Docs:** https://docs.comfy.org
- **Flux 2.0 Model:** https://huggingface.co/black-forest-labs/FLUX.2-dev

