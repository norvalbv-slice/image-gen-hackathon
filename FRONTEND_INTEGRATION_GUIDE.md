# AI Menu Image Generation - Frontend Integration Guide

> **For:** AI Agent working on Owners Portal (`owners-web` repo)  
> **Context:** Winter Hackathon 2025 - Deadline Nov 28, 2025  
> **Epic:** [sc-640877](https://app.shortcut.com/slicernd/epic/640877)

---

## 📖 Project Context

### What is This?

This is a **Winter Hackathon 2025** project for Slice Life. Slice is a platform that helps independent pizzerias compete with big chains by providing technology for online ordering, marketing, and operations.

**The hackathon runs Nov 25 - 1 Dec, 2025** - it's a fast-paced exploration to prove a concept.

### The Problem We're Solving

> *"We eat with our eyes first"*

Most pizza shops on Slice's platform have **poor or missing menu imagery**:
- Many menu items have no photos at all
- Existing photos are often low quality (phone pics, bad lighting)
- Professional food photography is expensive ($50-200 per dish)
- Shops don't have time or expertise to take good photos

This matters because:
- **New consumer-facing surfaces** (app redesign, web templates) lean heavily on imagery
- **Data shows** menu items with images get significantly more orders
- **First impressions** - a menu full of grey placeholder boxes looks unprofessional

### The Vision

**Single-click automation to give shops a menu full of great-looking AI-generated images.**

An owner clicks a button, selects their menu items, and within minutes has professional-looking food photography for their entire menu - at zero cost.

### Questions We're Answering

| Question | Type |
|----------|------|
| Can we generate *believable* images from just item names + descriptions? | Feasibility |
| Can one reference image style an entire menu consistently? | Feasibility |
| Can this scale to hundreds of shops, tens of thousands of images? | Viability |
| Will owners actually value and use the generated images? | Desirability |
| Could images go live without manual review? | Desirability |

### The Team

| Person | Role |
|--------|------|
| **Rick Monro** | Product Lead |
| **Daniele Baelde** | Frontend Lead (Owners Portal) |
| **David Robinson** | Frontend Engineer |
| **Benji Norval** | Backend Engineer (built the AI API) |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OWNERS PORTAL (Your Work)                        │
│  • React/Next.js frontend                                            │
│  • Menu items picker UI                                              │
│  • Scene/style selector                                              │
│  • Loading/progress screens                                          │
│  • Image preview & approval flow                                     │
│  • Save selected images to menu                                      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ HTTPS POST (JSON)
                                │ Authorization: Bearer $RUNPOD_API_KEY
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   RUNPOD SERVERLESS ENDPOINT (Done ✅)               │
│                                                                      │
│  Endpoint: hbvg2b5ucr59mx                                           │
│  Docker Image: benjithegreat/comfyui-flux2:fp8-v21                  │
│                                                                      │
│  What it does:                                                       │
│  • Runs ComfyUI + Flux 2.0 FP8 model on A100/L40S GPUs              │
│  • Generates 4 image variations per request (~25 seconds)           │
│  • Supports 6 predefined "scenes" (visual styles)                   │
│  • Supports reference image mode (extract style from existing photo)│
│  • Returns base64 PNG images ready for display                      │
└─────────────────────────────────────────────────────────────────────┘
```

### What's Already Built (Backend - Complete ✅)

| Feature | Status | Description |
|---------|--------|-------------|
| ComfyUI + Flux 2.0 | ✅ Done | State-of-the-art image generation model |
| Scene-based generation | ✅ Done | 6 predefined visual styles (rustic, modern, etc.) |
| Reference image mode | ✅ Done | Extract style from existing photo using GPT-5.1 |
| Multi-food support | ✅ Done | Works for pizza, pasta, salads, desserts, etc. |
| Angle variations | ✅ Done | Each batch generates 4 different compositions |
| RunPod deployment | ✅ Done | Serverless, auto-scaling, pay-per-use |

### What You're Building (Frontend - In Progress)

| Feature | Story | Status |
|---------|-------|--------|
| Menu link in sidebar | sc-642397 | ✅ Done |
| Menu images page | sc-642398 | ✅ Done |
| Menu items picker | sc-642400 | 🔄 In Review (PR #5317, #5318) |
| Description editor + disclaimer | sc-642401 | 🔄 In Review (PR #5319) |
| **Loading screen** | sc-642402 | 📋 TODO |
| **Preview screen** | sc-642403 | 📋 TODO |
| **Wire up the API** | - | 📋 TODO |
| References picker | sc-642399 | 📋 Nice-to-have |
| Generation notification | sc-642404 | 📋 Nice-to-have |

---

## TL;DR

You're integrating a **working RunPod serverless API** that generates AI food images using Flux 2.0. The backend is complete - your job is to build the frontend UI in the Owners Portal.

---

## 🎯 What You're Building

A flow in the Owners Portal where shop owners can:
1. Select menu items that need images
2. Optionally choose a reference image (for style consistency)
3. Generate AI images (~25 seconds per batch of 4)
4. Preview 4 angle variations and pick their favorite
5. Save selected images to their menu

---

## 🔌 API Reference

### Endpoint Details

| Property | Value |
|----------|-------|
| **Base URL** | `https://api.runpod.ai/v2/hbvg2b5ucr59mx` |
| **Auth Header** | `Authorization: Bearer ${RUNPOD_API_KEY}` |
| **Method** | Async (submit job → poll for result) |
| **Generation Time** | ~20-25 seconds for 4 images |

### Environment Variables Required

```env
RUNPOD_API_KEY=your_runpod_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # Only needed for reference image mode
```

---

## 📤 API Usage

### Option 1: Scene-Based Generation (Simple)

Use predefined visual styles. Best for quick implementation.

```typescript
// POST https://api.runpod.ai/v2/hbvg2b5ucr59mx/run
const response = await fetch('https://api.runpod.ai/v2/hbvg2b5ucr59mx/run', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    input: {
      item_name: "Pepperoni Pizza",              // Required
      item_description: "pepperoni, mozzarella, tomato sauce, fresh basil",  // Required
      scene: "rustic_italian",                   // Optional (default: rustic_italian)
      num_images: 4                              // Optional: 1-4 (default: 1)
    }
  })
});

const { id } = await response.json();
// Returns: { "id": "abc123-job-id", "status": "IN_QUEUE" }
```

#### Available Scenes

| Scene ID | Description | Best For |
|----------|-------------|----------|
| `rustic_italian` | Warm wood, traditional pizzeria | Classic Italian restaurants |
| `modern_minimal` | Clean white marble, Instagram-worthy | Modern cafes |
| `cozy_homestyle` | Checkered tablecloth, family-style | Family pizzerias |
| `premium_upscale` | Dark slate, dramatic lighting | Upscale restaurants |
| `industrial_craft` | Concrete, metal accents, artisan | Craft pizza shops |
| `garden_fresh` | Natural light, herbs, organic feel | Health-focused shops |

---

### Option 2: Reference Image Mode (Advanced)

Extract the visual style from an existing photo. Great for consistency across a menu.

```typescript
// Convert image to base64 first
const base64Image = await imageToBase64(existingMenuPhoto);

const response = await fetch('https://api.runpod.ai/v2/hbvg2b5ucr59mx/run', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    input: {
      item_name: "Penne Arrabbiata",
      item_description: "spicy tomato sauce, garlic, parsley, parmesan",
      reference_image: base64Image,              // Base64 PNG/WEBP/JPEG
      extract_scene: true,                       // Required for reference mode
      openai_api_key: process.env.OPENAI_API_KEY, // Required for scene extraction
      num_images: 4,
      use_img2img: false  // false = varied angles (recommended), true = same composition
    }
  })
});
```

**How it works:**
1. GPT-5.1 analyzes the reference image
2. Extracts: background, lighting, props, camera angle, color palette
3. Applies that style to generate the NEW food item
4. Works across food types (pizza reference → pasta output works!)

---

### Polling for Results

Jobs are async. Poll until `status === "COMPLETED"` or `"FAILED"`.

```typescript
async function pollForResult(jobId: string, maxWaitMs = 300000): Promise<GenerationResult> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWaitMs) {
    const response = await fetch(
      `https://api.runpod.ai/v2/hbvg2b5ucr59mx/status/${jobId}`,
      { headers: { 'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}` } }
    );
    
    const result = await response.json();
    
    if (result.status === 'COMPLETED') {
      return result.output;  // Contains the images!
    }
    
    if (result.status === 'FAILED') {
      throw new Error(result.output?.error || 'Generation failed');
    }
    
    // Status is IN_QUEUE or IN_PROGRESS - wait and retry
    await new Promise(resolve => setTimeout(resolve, 5000)); // Poll every 5s
  }
  
  throw new Error('Generation timed out');
}
```

---

## 📥 Response Format

```typescript
interface GenerationResponse {
  status: "success" | "failed";
  images: Array<{
    image_base64: string;      // PNG as base64 - use directly in <img src>
    seed: number;              // For reproducibility
    variation: {
      angle: string;           // e.g., "overhead flat lay shot"
      focus: string;           // e.g., "full dish centered"
      depth: string;           // e.g., "sharp focus throughout"
    };
    prompt: string;            // Full prompt used (for debugging)
  }>;
  scene: string;               // Scene ID used
  scene_name: string;          // Human-readable name
  num_images: number;
  item_type: string;           // Detected food type
  available_scenes: string[];  // All scene options
  
  // Only in reference mode:
  extracted_scene?: {
    name: string;
    background: string;
    lighting: string;
    props: string;
    camera_angle: string;
    detected_food_type: string;
    // ... more details
  };
}
```

### Displaying Images

```typescript
// The image_base64 is raw base64 - add the data URI prefix
const imgSrc = `data:image/png;base64,${image.image_base64}`;

// In React:
<img src={`data:image/png;base64,${image.image_base64}`} alt={image.variation.angle} />
```

---

## 🏗️ Complete React Hook Example

```typescript
// hooks/useImageGeneration.ts
import { useState, useCallback } from 'react';

const RUNPOD_ENDPOINT = 'https://api.runpod.ai/v2/hbvg2b5ucr59mx';

interface GenerateOptions {
  itemName: string;
  itemDescription: string;
  scene?: string;
  referenceImage?: string;  // base64
  numImages?: number;
}

interface GeneratedImage {
  image_base64: string;
  seed: number;
  variation: {
    angle: string;
    focus: string;
    depth: string;
  };
}

export function useImageGeneration() {
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [images, setImages] = useState<GeneratedImage[]>([]);

  const generate = useCallback(async (options: GenerateOptions) => {
    setIsLoading(true);
    setError(null);
    setProgress('Submitting job...');
    
    try {
      // 1. Submit the job
      const submitResponse = await fetch(`${RUNPOD_ENDPOINT}/run`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${process.env.NEXT_PUBLIC_RUNPOD_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          input: {
            item_name: options.itemName,
            item_description: options.itemDescription,
            scene: options.scene || 'rustic_italian',
            num_images: options.numImages || 4,
            // Reference image mode (optional)
            ...(options.referenceImage && {
              reference_image: options.referenceImage,
              extract_scene: true,
              openai_api_key: process.env.NEXT_PUBLIC_OPENAI_API_KEY,
              use_img2img: false
            })
          }
        })
      });
      
      const { id: jobId } = await submitResponse.json();
      setProgress('Generating images...');
      
      // 2. Poll for completion
      const startTime = Date.now();
      const maxWait = 5 * 60 * 1000; // 5 minutes
      
      while (Date.now() - startTime < maxWait) {
        const statusResponse = await fetch(`${RUNPOD_ENDPOINT}/status/${jobId}`, {
          headers: { 'Authorization': `Bearer ${process.env.NEXT_PUBLIC_RUNPOD_API_KEY}` }
        });
        
        const result = await statusResponse.json();
        
        if (result.status === 'COMPLETED') {
          setImages(result.output.images);
          setProgress('Complete!');
          return result.output;
        }
        
        if (result.status === 'FAILED') {
          throw new Error(result.output?.error || 'Generation failed');
        }
        
        // Update progress
        const elapsed = Math.round((Date.now() - startTime) / 1000);
        setProgress(`Generating... ${elapsed}s`);
        
        await new Promise(r => setTimeout(r, 3000)); // Poll every 3s
      }
      
      throw new Error('Generation timed out after 5 minutes');
      
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { generate, isLoading, progress, error, images };
}
```

---

## 📋 Remaining Frontend Stories

### In Review (PRs ready to merge)
| PR | Story | What it does |
|----|-------|--------------|
| [#5317](https://github.com/slicelife/owners-web/pull/5317) | sc-642400 | Inline description editing |
| [#5318](https://github.com/slicelife/owners-web/pull/5318) | sc-642400 | Menu images selector (has conflicts) |
| [#5319](https://github.com/slicelife/owners-web/pull/5319) | sc-642401 | Sort by missing descriptions + AI disclaimer |

### Backlog (Need Implementation)
| Story | Description | Priority |
|-------|-------------|----------|
| [sc-642402](https://app.shortcut.com/slicernd/story/642402) | **Loading Screen** - Show progress while generating | HIGH |
| [sc-642403](https://app.shortcut.com/slicernd/story/642403) | **Preview Screen** - Display 4 variations, pick favorite | HIGH |
| [sc-642399](https://app.shortcut.com/slicernd/story/642399) | **References Picker** - Upload/select reference images | MEDIUM |
| [sc-642404](https://app.shortcut.com/slicernd/story/642404) | **Generation Notification** - Toast when complete | LOW |

---

## 🎨 Suggested User Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. MENU ITEMS PICKER                                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ☑ Pepperoni Pizza - "pepperoni, mozzarella..."         ││
│  │ ☑ Margherita - "tomato, fresh mozzarella, basil"       ││
│  │ ☐ Garlic Knots - "garlic butter, parsley"              ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Scene: [rustic_italian ▼]     [Generate Images]            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. LOADING SCREEN                                           │
│                                                              │
│           🍕 Generating your menu images...                  │
│                                                              │
│           ████████████░░░░░░░░  45%                         │
│                                                              │
│           Pepperoni Pizza (2 of 4 images)                   │
│           Estimated: ~25 seconds remaining                   │
│                                                              │
│                      [Cancel]                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. PREVIEW SCREEN                                           │
│                                                              │
│  Pepperoni Pizza                                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │  IMG 1  │ │  IMG 2  │ │  IMG 3  │ │  IMG 4  │           │
│  │ overhead│ │ 45° ang │ │ closeup │ │ side    │           │
│  │   ✓     │ │         │ │         │ │         │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
│                                                              │
│  [← Back]                    [Save Selected] [Regenerate]   │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Important Notes

### Cold Starts
- **First request after idle:** May take 2-5 minutes (model loading)
- **Subsequent requests:** ~20-25 seconds for 4 images
- Show appropriate loading states for both scenarios

### Rate Limits
- Workers auto-scale, but be mindful of parallel requests
- Consider queuing if generating for many items at once

### Error Handling
```typescript
// Common error scenarios to handle:
const errorMessages = {
  'TIMEOUT': 'Generation took too long. Please try again.',
  'FAILED': 'Image generation failed. Check item description.',
  'NETWORK': 'Connection error. Check your internet.',
};
```

### Image Sizes
- Generated images are **1024x1024 PNG**
- Base64 strings are ~1-2MB each
- Consider compression before saving to your backend

---

## 🔗 Key Resources

| Resource | Link |
|----------|------|
| Epic | https://app.shortcut.com/slicernd/epic/640877 |
| Feature Branch | `fb/ai-image-gen-hackathon` |
| Slack Channel | `#proj-temp-ai-image-gen` |
| RunPod Dashboard | https://www.runpod.io/console/serverless |

### Team Contacts
- **Benji Norval** - Backend/RunPod (built this API)
- **Daniele Baelde** - Frontend lead
- **David Robinson** - Frontend
- **Rick Monro** - Product

---

## 🧪 Quick Test

Test the API works before integrating:

```bash
curl -X POST "https://api.runpod.ai/v2/hbvg2b5ucr59mx/run" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "item_name": "Pepperoni Pizza",
      "item_description": "pepperoni, mozzarella, tomato sauce",
      "scene": "rustic_italian",
      "num_images": 1
    }
  }'

# Returns job ID, then poll:
curl "https://api.runpod.ai/v2/hbvg2b5ucr59mx/status/YOUR_JOB_ID" \
  -H "Authorization: Bearer $RUNPOD_API_KEY"
```

---

## 💡 Key Learnings from Backend Development

These insights from building the backend may help with frontend decisions:

### What Makes Good Prompts

The AI generates better images when descriptions are specific:
- ✅ Good: `"pepperoni, mozzarella, fresh basil, tomato sauce, charred crust"`
- ❌ Bad: `"pizza with toppings"`

Consider adding a "enhance description" feature or prompting users to add ingredients.

### The 4 Variations Are Different Angles

Each generation produces 4 images with different compositions:
1. **Overhead flat lay** - Top-down view
2. **45-degree angle** - Classic food photography angle
3. **Low angle / eye-level** - Dramatic, appetizing
4. **Close-up macro** - Detail shot

These are intentionally varied so owners can pick their favorite. Display them with labels!

### Reference Image Mode is Powerful

If a shop has ONE good photo, reference mode can style their entire menu consistently:
- Extracts: background surface, lighting, props, color palette
- Works across food types (pizza photo → pasta output)
- Creates cohesive visual branding

Consider making this a prominent feature, not just an afterthought.

### Cold Starts Are Real

The first request after the system has been idle will be slow:
- **Cold start:** 2-5 minutes (downloading 54GB model)
- **Warm:** 20-25 seconds

**UX Suggestion:** Show a different message for cold starts. Maybe: *"Warming up the AI kitchen... this may take a few minutes the first time."*

### Image Quality Depends on Descriptions

The AI can only work with what it's given. Empty or vague descriptions = generic images.

**UX Suggestion:** Filter out or warn about items with no description. The existing PRs already sort by missing descriptions - good pattern!

---

## 🚀 Hackathon Rules (Context)

Since this is a hackathon, the rules are **relaxed**:

1. **Speed over perfection** - Get it working first, refine later
2. **Experimentation encouraged** - Try things, iterate quickly
3. **Scope is flexible** - Can tackle larger chunks to move fast
4. **Don't over-engineer** - Simple solutions are fine
5. **Still use conventional commits** - Keep history readable

The goal is a **working demo**, not production-ready code. Focus on the happy path.

---

## 📁 Existing PRs to Reference

These PRs show the patterns being used in the owners-web codebase:

| PR | What to Learn From It |
|----|----------------------|
| [#5317](https://github.com/slicelife/owners-web/pull/5317) | Inline editing pattern, mutation hooks |
| [#5318](https://github.com/slicelife/owners-web/pull/5318) | Image selection UI, grid layout, checkboxes |
| [#5319](https://github.com/slicelife/owners-web/pull/5319) | Sorting logic, optimistic updates, Alert component |

All PRs are against `fb/ai-image-gen-hackathon` feature branch.

---

## ✅ Definition of Done

For the hackathon demo to be successful, we need:

1. [ ] Owner can see menu items without images
2. [ ] Owner can select items to generate images for
3. [ ] Owner can choose a visual style (scene)
4. [ ] System calls RunPod API and shows loading state
5. [ ] Owner sees 4 generated variations per item
6. [ ] Owner can select their favorite
7. [ ] Selected images are saved (even if just to state for demo)

Nice-to-haves (if time permits):
- [ ] Reference image upload
- [ ] Notification when generation completes
- [ ] Regenerate individual items
- [ ] Batch generation for multiple items

---

*Last updated: Nov 28, 2025 by Benji Norval*

*Questions? Reach out on Slack: `#proj-temp-ai-image-gen`*

