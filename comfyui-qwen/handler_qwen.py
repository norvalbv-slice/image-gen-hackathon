"""
RunPod Serverless Handler for ComfyUI + Qwen-Image-2512 (GGUF Q8)
Features:
- Multi-image generation (num_images param)
- Menu item templates (pizza, pasta, salad, dessert, etc.)
- LLM as judge for auto-selecting best image
- Reference image scene extraction (GPT-4V analyzes reference to create scene)
- Reference image visual conditioning (img2img for consistency)
"""

import runpod
import json
import subprocess
import time
import os
import base64
import glob
import random
import requests
import shutil
import sys
import io
from huggingface_hub import hf_hub_download
from PIL import Image

# Configuration
COMFYUI_PATH = os.environ.get("COMFYUI_PATH", "/comfyui")
WORKFLOW_PATH = "/workflow.json"
WORKFLOW_IMG2IMG_PATH = "/workflow_img2img.json"
TEMPLATES_PATH = "/templates.json"
SCENES_PATH = "/scenes.json"
OUTPUT_DIR = f"{COMFYUI_PATH}/output"
INPUT_DIR = f"{COMFYUI_PATH}/input"
COMFYUI_PORT = 8188

# Remote config URLs (for live editing without Docker rebuild)
SCENES_URL = os.environ.get("SCENES_URL", None)
TEMPLATES_URL = os.environ.get("TEMPLATES_URL", None)

# Cache for remote configs (refresh every N seconds)
CONFIG_CACHE = {}
CONFIG_CACHE_TTL = 60

# Model paths within ComfyUI (official safetensors paths)
DIFFUSION_PATH = f"{COMFYUI_PATH}/models/diffusion_models"
VAE_PATH = f"{COMFYUI_PATH}/models/vae"
TEXT_ENCODER_PATH = f"{COMFYUI_PATH}/models/text_encoders"


def ensure_models_downloaded():
    """Download Qwen-Image-2512 official safetensors models using huggingface_hub"""
    diffusion_file = f"{DIFFUSION_PATH}/qwen_image_2512_fp8_e4m3fn.safetensors"

    if os.path.exists(diffusion_file):
        print("Models already present")
        return

    print("Downloading Qwen-Image-2512 official models using huggingface_hub...")

    # Create directories
    os.makedirs(DIFFUSION_PATH, exist_ok=True)
    os.makedirs(VAE_PATH, exist_ok=True)
    os.makedirs(TEXT_ENCODER_PATH, exist_ok=True)

    # Download Diffusion Model (FP8 ~20GB)
    print("Downloading Qwen-Image-2512 Diffusion Model (FP8 ~20GB)...")
    hf_hub_download(
        repo_id="Comfy-Org/Qwen-Image_ComfyUI",
        filename="split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors",
        local_dir=DIFFUSION_PATH,
        local_dir_use_symlinks=False,
    )
    # Move from subdirectory to expected location
    src = f"{DIFFUSION_PATH}/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors"
    dst = f"{DIFFUSION_PATH}/qwen_image_2512_fp8_e4m3fn.safetensors"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
    print("Downloaded Diffusion Model")

    # Download Text Encoder (FP8 ~15GB)
    print("Downloading Qwen2.5-VL Text Encoder (FP8 ~15GB)...")
    hf_hub_download(
        repo_id="Comfy-Org/Qwen-Image_ComfyUI",
        filename="split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        local_dir=TEXT_ENCODER_PATH,
        local_dir_use_symlinks=False,
    )
    # Move from subdirectory to expected location
    src = f"{TEXT_ENCODER_PATH}/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors"
    dst = f"{TEXT_ENCODER_PATH}/qwen_2.5_vl_7b_fp8_scaled.safetensors"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
    print("Downloaded Text Encoder")

    # Download VAE (~254MB)
    print("Downloading Qwen-Image VAE (~254MB)...")
    hf_hub_download(
        repo_id="Comfy-Org/Qwen-Image_ComfyUI",
        filename="split_files/vae/qwen_image_vae.safetensors",
        local_dir=VAE_PATH,
        local_dir_use_symlinks=False,
    )
    # Move from subdirectory to expected location
    src = f"{VAE_PATH}/split_files/vae/qwen_image_vae.safetensors"
    dst = f"{VAE_PATH}/qwen_image_vae.safetensors"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
    print("Downloaded VAE")

    print("All Qwen models downloaded! Total: ~36GB")


def load_workflow():
    with open(WORKFLOW_PATH, "r") as f:
        return json.load(f)


def load_workflow_img2img():
    """Load the img2img workflow for reference-based generation."""
    try:
        with open(WORKFLOW_IMG2IMG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("img2img workflow not found, using standard workflow")
        return load_workflow()


def save_reference_for_workflow(image_base64: str, max_size: int = 1024) -> str:
    """Save reference image to ComfyUI input folder for img2img workflow.

    Resizes large images to max_size to prevent VRAM issues during VAE encoding.
    """
    os.makedirs(INPUT_DIR, exist_ok=True)
    ref_path = os.path.join(INPUT_DIR, "reference.png")

    image_data = base64.b64decode(image_base64)

    # Load image and resize if needed
    img = Image.open(io.BytesIO(image_data))
    original_size = img.size

    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        print(f"Resized reference image from {original_size} to {img.size}")

    # Convert to RGB if needed (handles RGBA, palette modes)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    img.save(ref_path, "PNG")
    file_size = os.path.getsize(ref_path)

    print(f"Saved reference image to {ref_path} ({file_size} bytes, size={img.size})")
    return ref_path


def load_templates():
    """Load menu item templates - from URL if set, otherwise local file."""
    if TEMPLATES_URL:
        remote_data = fetch_remote_config(TEMPLATES_URL, "templates")
        if remote_data:
            return remote_data

    try:
        with open(TEMPLATES_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Templates file not found, using defaults")
        return {}


def fetch_remote_config(url, cache_key):
    """Fetch config from URL with caching."""
    now = time.time()

    if cache_key in CONFIG_CACHE:
        cached_data, cached_time = CONFIG_CACHE[cache_key]
        if now - cached_time < CONFIG_CACHE_TTL:
            return cached_data

    try:
        print(f"Fetching config from {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        CONFIG_CACHE[cache_key] = (data, now)
        print(f"Successfully loaded config from {url}")
        return data
    except Exception as e:
        print(f"Failed to fetch from {url}: {e}")
        if cache_key in CONFIG_CACHE:
            return CONFIG_CACHE[cache_key][0]
        return None


def load_scenes():
    """Load scene configurations - from URL if set, otherwise local file."""
    if SCENES_URL:
        remote_data = fetch_remote_config(SCENES_URL, "scenes")
        if remote_data:
            return remote_data

    try:
        with open(SCENES_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Scenes file not found, using defaults")
        return {}


def get_available_scenes():
    """Return list of available scene names."""
    scenes = load_scenes()
    return list(scenes.keys())


def get_template():
    """Get the universal default template from templates.json."""
    templates = load_templates()
    return templates.get("default", {})


def detect_item_type(item_name: str, item_description: str = "") -> str:
    """Return the item name as the type identifier.

    Prompt construction is fully universal and does not depend on categorization.
    This exists only for API response metadata compatibility.
    """
    return item_name.lower().strip()


def build_scene_prompt(
    item_name: str, item_description: str, scene_id: str, variation_index: int = 0
) -> dict:
    """Build a prompt using universal hierarchical structure with scene configuration.

    Hierarchy (research-backed for preventing style bleed):
    1. Camera directive (highest emphasis) - anchors the composition
    2. Food anchor (item_name as primary subject) - prevents category confusion
    3. Description + distribution - natural ingredient presentation
    4. Scene elements - background, lighting, mood, props
    5. Orientation + quality - gravity, realism, photography specs
    """
    scenes = load_scenes()

    if scene_id not in scenes:
        print(f"Scene '{scene_id}' not found, using rustic_italian")
        scene_id = "rustic_italian"

    scene = scenes[scene_id]
    template = get_template()
    variations = scene.get("variations", [])

    if variations:
        variation = variations[variation_index % len(variations)]
    else:
        variation = {
            "label": "Overhead",
            "angle": "overhead",
            "focus": "centered",
            "depth": "sharp focus",
        }

    # Universal hierarchical prompt structure
    prompt_parts = [
        # 1. Camera directive (triple emphasis = highest priority for Qwen)
        f"((({variation.get('angle', '')})))" if variation.get("angle") else "",
        f"(({variation.get('focus', '')}))" if variation.get("focus") else "",
        f"({variation.get('depth', '')})" if variation.get("depth") else "",
        # 2. Food anchor - item_name IS the anchor, no category mapping needed
        "professional food photography",
        f"(({item_name}))",
        # 3. Description de-emphasized so dish name drives the visual, ingredients refine
        f"[{item_description}]",
        template.get("distribution", ""),
        # 4. Scene elements (style isolated from food identity)
        scene.get(
            "realism",
            "authentic handmade appearance with natural imperfections, real food texture not CGI or plastic",
        ),
        scene.get("background", ""),
        scene.get("lighting", ""),
        scene.get("mood", ""),
        scene.get("props", ""),
        # 5. Orientation + quality
        "dish right-side up on table with correct gravity and natural orientation",
        template.get("suffix", ""),
        "editorial food photography, high resolution, appetizing, shot on Canon 5D Mark IV",
    ]

    full_prompt = ", ".join(part for part in prompt_parts if part)

    return {
        "prompt": full_prompt,
        "scene_id": scene_id,
        "scene_name": scene.get("name", scene_id),
        "variation_index": variation_index,
        "variation": variation,
    }


def build_prompt(
    item_name: str, item_description: str, item_type: str = None, templates: dict = None
) -> str:
    """Build a complete prompt using the universal hierarchical structure."""
    template = get_template()

    parts = [
        # Food anchor first - item_name is the primary subject
        "professional food photography",
        f"(({item_name}))",
        f"[{item_description}]",
        template.get("distribution", ""),
        template.get("suffix", ""),
        template.get("background", ""),
        template.get("lighting", ""),
        template.get("camera", ""),
        "dish right-side up on table with correct gravity and natural orientation",
        "inviting and delicious mood",
    ]

    return ", ".join(part for part in parts if part)


def update_workflow_prompt(workflow, positive_prompt, negative_prompt=None, seed=None):
    """Update workflow with prompt and seed."""
    workflow = json.loads(json.dumps(workflow))  # Deep copy

    if "6" in workflow:
        workflow["6"]["inputs"]["text"] = positive_prompt
    if negative_prompt and "7" in workflow:
        workflow["7"]["inputs"]["text"] = negative_prompt
    if "10" in workflow:
        workflow["10"]["inputs"]["seed"] = (
            seed if seed is not None else random.randint(0, 2**32 - 1)
        )
    return workflow


def start_comfyui_server():
    return subprocess.Popen(
        [
            "python",
            "main.py",
            "--listen",
            "127.0.0.1",
            "--port",
            str(COMFYUI_PORT),
            "--disable-auto-launch",
        ],
        cwd=COMFYUI_PATH,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def wait_for_server(timeout=120):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if (
                requests.get(
                    f"http://127.0.0.1:{COMFYUI_PORT}/system_stats"
                ).status_code
                == 200
            ):
                print("ComfyUI server is ready")
                return True
        except:
            pass
        time.sleep(1)
    raise TimeoutError("ComfyUI server failed to start")


def queue_prompt(workflow):
    response = requests.post(
        f"http://127.0.0.1:{COMFYUI_PORT}/prompt", json={"prompt": workflow}
    )
    if response.status_code != 200:
        raise RuntimeError(f"Failed to queue prompt: {response.text}")
    return response.json()["prompt_id"]


def wait_for_completion(prompt_id, timeout=300):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"http://127.0.0.1:{COMFYUI_PORT}/history/{prompt_id}"
            )
            if response.status_code == 200 and prompt_id in response.json():
                return response.json()[prompt_id]
        except:
            pass
        time.sleep(1)
    raise TimeoutError("Prompt execution timed out")


def get_latest_image():
    images = glob.glob(f"{OUTPUT_DIR}/*.png")
    if not images:
        raise FileNotFoundError("No output images found")
    return max(images, key=os.path.getctime)


def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def cleanup_outputs():
    for f in glob.glob(f"{OUTPUT_DIR}/*.png"):
        try:
            os.remove(f)
        except:
            pass


def save_reference_images(reference_images_b64: list) -> list:
    """Save base64 reference images to temp files for ComfyUI."""
    saved_paths = []
    input_dir = f"{COMFYUI_PATH}/input"
    os.makedirs(input_dir, exist_ok=True)

    for i, img_b64 in enumerate(reference_images_b64):
        filepath = f"{input_dir}/ref_{i}.png"
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(img_b64))
        saved_paths.append(filepath)
        print(f"Saved reference image: {filepath}")

    return saved_paths


def cleanup_reference_images():
    """Clean up temporary reference images."""
    input_dir = f"{COMFYUI_PATH}/input"
    for f in glob.glob(f"{input_dir}/ref_*.png"):
        try:
            os.remove(f)
        except:
            pass


def generate_single_image(workflow, positive_prompt, negative_prompt, seed):
    """Generate a single image and return base64 + seed."""
    cleanup_outputs()
    updated_workflow = update_workflow_prompt(
        workflow, positive_prompt, negative_prompt, seed
    )
    actual_seed = updated_workflow["10"]["inputs"]["seed"]

    print(f"[WORKFLOW DEBUG] Generating with seed {actual_seed}")
    print(f"[WORKFLOW DEBUG] Nodes in workflow: {list(updated_workflow.keys())}")

    if "13" in updated_workflow:
        print(f"[WORKFLOW DEBUG] LoadImage node 13: {updated_workflow['13']['inputs']}")
        print(f"[WORKFLOW DEBUG] This is IMG2IMG mode")
    else:
        print(f"[WORKFLOW DEBUG] This is TEXT2IMG mode (no LoadImage node)")

    if "10" in updated_workflow:
        latent_input = updated_workflow["10"]["inputs"].get("latent_image")
        print(f"[WORKFLOW DEBUG] KSampler latent_image source: {latent_input}")

    print(f"[WORKFLOW DEBUG] Prompt (first 200 chars): {positive_prompt[:200]}...")

    prompt_id = queue_prompt(updated_workflow)
    wait_for_completion(prompt_id)

    image_path = get_latest_image()
    image_base64 = image_to_base64(image_path)
    print(f"[WORKFLOW DEBUG] Generated image: {image_path}")

    return {"image_base64": image_base64, "seed": actual_seed}


comfyui_process = None
initialized = False


def handler(event):
    global comfyui_process, initialized, SCENES_URL, TEMPLATES_URL

    try:
        if not initialized:
            print("Initializing - downloading models if needed...")
            ensure_models_downloaded()
            initialized = True

        job_input = event.get("input", {})

        # DEV MODE: Allow overriding config URLs per-request
        request_scenes_url = job_input.get("scenes_url")
        request_templates_url = job_input.get("templates_url")

        if request_scenes_url:
            print(f"DEV MODE: Using custom scenes_url: {request_scenes_url}")
            SCENES_URL = request_scenes_url
            CONFIG_CACHE.pop("scenes", None)

        if request_templates_url:
            print(f"DEV MODE: Using custom templates_url: {request_templates_url}")
            TEMPLATES_URL = request_templates_url
            CONFIG_CACHE.pop("templates", None)

        workflow = load_workflow()
        templates = load_templates()

        # Get input parameters
        item_name = job_input.get("item_name", "pepperoni pizza")
        item_description = job_input.get("item_description", "classic toppings")
        item_type = job_input.get("item_type")
        num_images = min(max(job_input.get("num_images", 1), 1), 4)

        scene = job_input.get("scene")
        requested_variation_index = job_input.get("variation_index")

        reference_image = job_input.get("reference_image")
        extract_scene = job_input.get("extract_scene", False)
        save_scene_as = job_input.get("save_scene_as")

        openai_api_key = job_input.get("openai_api_key") or os.environ.get(
            "OPENAI_API_KEY"
        )

        print("=" * 60)
        print("=== INCOMING PARAMETERS (Qwen-Image-2512) ===")
        print(f"  item_name: {item_name}")
        print(
            f"  item_description: {item_description[:50] if item_description else 'None'}..."
        )
        print(f"  num_images: {num_images}")
        print(f"  scene: {scene}")
        print(
            f"  reference_image: {'Yes (' + str(len(reference_image)) + ' chars)' if reference_image else 'None'}"
        )
        print(f"  extract_scene: {extract_scene}")
        print(f"  variation_index: {requested_variation_index}")
        print(
            f"  openai_api_key: {'Set (' + openai_api_key[:10] + '...)' if openai_api_key else 'NOT SET'}"
        )
        print(f"  save_scene_as: {save_scene_as}")
        print("=" * 60)

        reference_images = job_input.get("reference_images", [])

        ref_paths = []
        if reference_images:
            print(f"Received {len(reference_images)} reference images")
            ref_paths = save_reference_images(reference_images[:4])

        negative_prompt = job_input.get("negative_prompt", "")

        if comfyui_process is None or comfyui_process.poll() is not None:
            print("Starting ComfyUI server...")
            comfyui_process = start_comfyui_server()
            wait_for_server()

        results = []
        base_seed = job_input.get("seed")
        extracted_scene = None

        print(f"[CONDITION CHECK] reference_image truthy: {bool(reference_image)}")
        print(f"[CONDITION CHECK] extract_scene truthy: {bool(extract_scene)}")
        print(f"[CONDITION CHECK] Will enter reference mode: {bool(reference_image)}")

        # SIMPLE IMG2IMG MODE (reference image without GPT extraction)
        if reference_image and not extract_scene:
            print("=" * 60)
            print("=== SIMPLE IMG2IMG MODE (no GPT extraction) ===")
            print("=" * 60)

            ref_path = save_reference_for_workflow(reference_image)
            print(f"[REFERENCE SAVED TO]: {ref_path}")

            selected_workflow = load_workflow_img2img()
            denoise = job_input.get("denoise", 0.50)
            selected_workflow["10"]["inputs"]["denoise"] = denoise
            print(f"[DENOISE]: {denoise} (lower = more similar to reference)")

            for i in range(num_images):
                actual_variation_index = (
                    requested_variation_index
                    if requested_variation_index is not None
                    else i
                )

                if scene:
                    prompt_data = build_scene_prompt(
                        item_name, item_description, scene, actual_variation_index
                    )
                    positive_prompt = prompt_data["prompt"]
                    variation = prompt_data["variation"]
                else:
                    positive_prompt = build_prompt(
                        item_name, item_description, item_type, templates
                    )
                    variation = {
                        "label": "Default",
                        "angle": "default",
                        "focus": "centered",
                        "depth": "sharp",
                    }

                # Spread seeds to ensure visual difference between variations
                if base_seed is not None:
                    seed = base_seed + (i * 1000)
                else:
                    seed = random.randint(0, 2**32 - 1)

                print(f"\n[IMAGE {i + 1}/{num_images}]")
                print(f"[PROMPT]: {positive_prompt[:200]}...")
                print(f"[GENERATING]: img2img variation {i + 1}/{num_images}")

                result = generate_single_image(
                    selected_workflow, positive_prompt, negative_prompt, seed
                )

                result["variation"] = variation
                result["variation_index"] = actual_variation_index
                result["prompt"] = positive_prompt
                result["denoise"] = denoise
                results.append(result)

            response = {
                "images": results,
                "scene": scene,
                "scene_name": load_scenes().get(scene, {}).get("name", scene)
                if scene
                else "Custom",
                "item_type": item_type or detect_item_type(item_name, item_description),
                "num_images": num_images,
                "denoise": denoise,
                "status": "success",
                "mode": "img2img_simple",
                "model": "qwen-image-2512-Q8",
            }
            response["available_scenes"] = get_available_scenes()
            print(
                f"Generated {num_images} image(s) successfully via simple img2img mode"
            )
            return response

        # REFERENCE IMAGE MODE WITH GPT EXTRACTION
        if reference_image and extract_scene:
            print("=" * 60)
            print("=== REFERENCE IMAGE MODE ACTIVATED ===")
            print("=" * 60)
            try:
                from scene_extractor import (
                    extract_scene_from_image,
                    build_prompt_from_extracted_scene,
                )

                print(
                    "\n[STEP 1] Extracting scene from reference image using GPT-5.1..."
                )
                if not openai_api_key:
                    raise ValueError(
                        "OPENAI_API_KEY not set. Pass 'openai_api_key' in request or set env var."
                    )
                extracted_scene = extract_scene_from_image(
                    reference_image, api_key=openai_api_key
                )
                print(
                    f"[EXTRACTED SCENE NAME]: {extracted_scene.get('name', 'Unknown')}"
                )
                print("[EXTRACTED SCENE FULL]:")
                for key, value in extracted_scene.items():
                    print(f"  - {key}: {value}")

                use_img2img = job_input.get("use_img2img", True)

                print("\n[STEP 2] Generation mode:")
                print(
                    f"  Reference food: {extracted_scene.get('detected_food_type', 'unknown')}"
                )
                print(f"  Target item: {item_name}")
                print(f"  Use img2img (preserve shape): {use_img2img}")

                if use_img2img:
                    print("\n[STEP 3] Using IMG2IMG workflow (preserving composition)")
                    ref_path = save_reference_for_workflow(reference_image)
                    print(f"[REFERENCE SAVED TO]: {ref_path}")

                    if os.path.exists(ref_path):
                        file_size = os.path.getsize(ref_path)
                        print(f"[REFERENCE FILE EXISTS]: Yes, size={file_size} bytes")

                    selected_workflow = load_workflow_img2img()
                    denoise = job_input.get("denoise", 0.50)
                    selected_workflow["10"]["inputs"]["denoise"] = denoise
                    print(f"[DENOISE]: {denoise} (lower = more similar to reference)")
                    generation_mode = "reference_img2img"
                else:
                    print(
                        "\n[STEP 3] Using TEXT2IMG workflow (fresh generation with scene style)"
                    )
                    selected_workflow = load_workflow()
                    denoise = 1.0
                    generation_mode = "reference_scene_only"
                    print(f"[MODE]: Text-to-image with extracted scene styling")

                apply_variations = True

                for i in range(num_images):
                    actual_variation_index = (
                        requested_variation_index
                        if requested_variation_index is not None
                        else i
                    )

                    prompt_data = build_prompt_from_extracted_scene(
                        item_name,
                        item_description,
                        extracted_scene,
                        actual_variation_index,
                        apply_angle_variations=apply_variations,
                    )
                    positive_prompt = prompt_data["prompt"]
                    print(f"\n[IMAGE {i + 1}/{num_images}]")
                    print(f"[FULL PROMPT]: {positive_prompt}")

                    # Spread seeds to ensure visual difference between variations
                    if base_seed is not None:
                        seed = base_seed + (i * 1000)
                    else:
                        seed = random.randint(0, 2**32 - 1)

                    print(
                        f"[GENERATING]: {generation_mode} variation {i + 1}/{num_images}, seed={seed}"
                    )
                    result = generate_single_image(
                        selected_workflow, positive_prompt, negative_prompt, seed
                    )
                    print(
                        f"[GENERATED]: seed={result.get('seed')}, has_image={bool(result.get('image_base64'))}"
                    )

                    result["variation"] = prompt_data["variation"]
                    result["camera_angle"] = prompt_data.get("camera_angle", "")
                    result["variation_index"] = actual_variation_index
                    result["prompt"] = positive_prompt
                    result["denoise"] = denoise
                    results.append(result)

                print("\n" + "=" * 60)
                print("=== REFERENCE MODE COMPLETE ===")
                print("=" * 60)

                response = {
                    "images": results,
                    "extracted_scene": extracted_scene,
                    "scene_name": extracted_scene.get("name", "Custom Style"),
                    "item_type": item_type
                    or detect_item_type(item_name, item_description),
                    "num_images": num_images,
                    "denoise": denoise,
                    "status": "success",
                    "mode": generation_mode,
                    "used_img2img": use_img2img,
                    "model": "qwen-image-2512-Q8",
                }

                if save_scene_as:
                    response["scene_id"] = save_scene_as
                    response["save_scene_as"] = save_scene_as
                    print(f"[SCENE SAVED AS]: {save_scene_as}")

                response["available_scenes"] = get_available_scenes()
                print(
                    f"Generated {num_images} image(s) successfully via reference mode"
                )
                return response

            except Exception as e:
                print(f"Scene extraction failed: {e}")
                import traceback

                traceback.print_exc()
                scene = "rustic_italian"
                extracted_scene = None

        # SCENE-BASED GENERATION
        if not extracted_scene and scene:
            if requested_variation_index is not None:
                print(
                    f"Using scene: {scene} with SPECIFIC variation_index={requested_variation_index}"
                )
            else:
                print(f"Using scene: {scene} with {num_images} variations")

            for i in range(num_images):
                actual_variation_index = (
                    requested_variation_index
                    if requested_variation_index is not None
                    else i
                )

                prompt_data = build_scene_prompt(
                    item_name, item_description, scene, actual_variation_index
                )
                positive_prompt = prompt_data["prompt"]

                # Spread seeds to ensure visual difference between variations
                if base_seed is not None:
                    seed = base_seed + (i * 1000)
                else:
                    seed = random.randint(0, 2**32 - 1)

                print(
                    f"Generating image {i + 1}/{num_images} with variation_index={actual_variation_index}: {prompt_data['variation']}"
                )
                result = generate_single_image(
                    workflow, positive_prompt, negative_prompt, seed
                )

                result["variation"] = prompt_data["variation"]
                result["variation_index"] = actual_variation_index
                result["prompt"] = positive_prompt
                results.append(result)

            response = {
                "images": results,
                "scene": scene,
                "scene_name": load_scenes().get(scene, {}).get("name", scene),
                "item_type": item_type or detect_item_type(item_name, item_description),
                "num_images": num_images,
                "status": "success",
                "model": "qwen-image-2512-Q8",
            }

        # LEGACY MODE
        else:
            positive_prompt = job_input.get("positive_prompt")
            if not positive_prompt:
                positive_prompt = build_prompt(
                    item_name, item_description, item_type, templates
                )

            for i in range(num_images):
                # Spread seeds to ensure visual difference between variations
                if base_seed is not None:
                    seed = base_seed + (i * 1000)
                else:
                    seed = random.randint(0, 2**32 - 1)
                print(f"Generating image {i + 1}/{num_images}...")
                result = generate_single_image(
                    workflow, positive_prompt, negative_prompt, seed
                )
                result["prompt"] = positive_prompt
                results.append(result)

            response = {
                "images": results,
                "prompt": positive_prompt,
                "item_type": item_type or detect_item_type(item_name, item_description),
                "num_images": num_images,
                "status": "success",
                "model": "qwen-image-2512-Q8",
            }

        if ref_paths:
            cleanup_reference_images()
            response["reference_images_used"] = len(ref_paths)

        response["available_scenes"] = get_available_scenes()

        print(f"Generated {num_images} image(s) successfully")
        return response

    except TimeoutError as e:
        print(f"TIMEOUT ERROR: {str(e)}")
        print("Worker will exit to allow fresh restart...")
        import traceback

        traceback.print_exc()
        # Exit the worker so RunPod spins up a fresh one
        sys.exit(1)

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"error": str(e), "status": "failed"}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
