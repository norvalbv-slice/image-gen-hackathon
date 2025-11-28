"""
RunPod Serverless Handler for ComfyUI + Flux 2.0 (Slim Version)
Features:
- Multi-image generation (num_images param)
- Menu item templates (pizza, pasta, salad, dessert, etc.)
- LLM as judge for auto-selecting best image
- Reference image scene extraction (GPT-4V analyzes reference to create scene)
- Reference image visual conditioning (Flux uses reference for consistency)
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
from huggingface_hub import hf_hub_download

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
# Set these in RunPod template env vars or pass via API
SCENES_URL = os.environ.get("SCENES_URL", None)
TEMPLATES_URL = os.environ.get("TEMPLATES_URL", None)

# Cache for remote configs (refresh every N seconds)
CONFIG_CACHE = {}
CONFIG_CACHE_TTL = 60  # Refresh every 60 seconds

# Model paths within ComfyUI (matching where loaders expect files)
DIFFUSION_PATH = f"{COMFYUI_PATH}/models/diffusion_models"
VAE_PATH = f"{COMFYUI_PATH}/models/vae"
TEXT_ENCODER_PATH = f"{COMFYUI_PATH}/models/text_encoders"


def ensure_models_downloaded():
    """Download official FP8 models using huggingface_hub"""
    unet_file = f"{DIFFUSION_PATH}/flux2_dev_fp8mixed.safetensors"

    if os.path.exists(unet_file):
        print("Models already present")
        return

    print("Downloading Flux 2.0 FP8 models using huggingface_hub...")

    # Create directories
    os.makedirs(DIFFUSION_PATH, exist_ok=True)
    os.makedirs(VAE_PATH, exist_ok=True)
    os.makedirs(TEXT_ENCODER_PATH, exist_ok=True)

    # Download FP8 diffusion model (~35.5GB)
    print("Downloading Flux 2.0 FP8 diffusion model (~35.5GB)...")
    hf_hub_download(
        repo_id="Comfy-Org/flux2-dev",
        filename="split_files/diffusion_models/flux2_dev_fp8mixed.safetensors",
        local_dir=DIFFUSION_PATH,
        local_dir_use_symlinks=False,
    )
    # Move from subdirectory to expected location
    src = (
        f"{DIFFUSION_PATH}/split_files/diffusion_models/flux2_dev_fp8mixed.safetensors"
    )
    dst = f"{DIFFUSION_PATH}/flux2_dev_fp8mixed.safetensors"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
    print("Downloaded diffusion model")

    # Download VAE (~320MB)
    print("Downloading Flux 2.0 VAE (~320MB)...")
    hf_hub_download(
        repo_id="Comfy-Org/flux2-dev",
        filename="split_files/vae/flux2-vae.safetensors",
        local_dir=VAE_PATH,
        local_dir_use_symlinks=False,
    )
    src = f"{VAE_PATH}/split_files/vae/flux2-vae.safetensors"
    dst = f"{VAE_PATH}/flux2-vae.safetensors"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
    print("Downloaded VAE")

    # Download Text Encoder (~18GB)
    print("Downloading Mistral Text Encoder (~18GB)...")
    hf_hub_download(
        repo_id="Comfy-Org/flux2-dev",
        filename="split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors",
        local_dir=TEXT_ENCODER_PATH,
        local_dir_use_symlinks=False,
    )
    src = f"{TEXT_ENCODER_PATH}/split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors"
    dst = f"{TEXT_ENCODER_PATH}/mistral_3_small_flux2_fp8.safetensors"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.move(src, dst)
    print("Downloaded Text Encoder")

    print("All models downloaded! Total: ~54GB")


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


def save_reference_for_workflow(image_base64: str) -> str:
    """Save reference image to ComfyUI input folder for img2img workflow."""
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    # Save as reference.png (the workflow expects this filename)
    ref_path = os.path.join(INPUT_DIR, "reference.png")
    
    image_data = base64.b64decode(image_base64)
    with open(ref_path, "wb") as f:
        f.write(image_data)
    
    print(f"Saved reference image to {ref_path} ({len(image_data)} bytes)")
    return ref_path


def load_templates():
    """Load menu item templates - from URL if set, otherwise local file."""
    # Try remote URL first (for live editing)
    if TEMPLATES_URL:
        remote_data = fetch_remote_config(TEMPLATES_URL, "templates")
        if remote_data:
            return remote_data

    # Fall back to local file
    try:
        with open(TEMPLATES_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Templates file not found, using defaults")
        return {}


def fetch_remote_config(url, cache_key):
    """Fetch config from URL with caching."""
    now = time.time()

    # Check cache
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
        # Return cached data if available (even if stale)
        if cache_key in CONFIG_CACHE:
            return CONFIG_CACHE[cache_key][0]
        return None


def load_scenes():
    """Load scene configurations - from URL if set, otherwise local file."""
    # Try remote URL first (for live editing)
    if SCENES_URL:
        remote_data = fetch_remote_config(SCENES_URL, "scenes")
        if remote_data:
            return remote_data

    # Fall back to local file
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


def build_scene_prompt(
    item_name: str, item_description: str, scene_id: str, variation_index: int = 0
) -> dict:
    """
    Build a prompt using scene configuration with specific variation.
    Returns dict with prompt and metadata about the variation used.
    """
    scenes = load_scenes()

    # Default to rustic_italian if scene not found
    if scene_id not in scenes:
        print(f"Scene '{scene_id}' not found, using rustic_italian")
        scene_id = "rustic_italian"

    scene = scenes[scene_id]
    variations = scene.get("variations", [])

    # Get the specific variation (wrap around if index exceeds available)
    if variations:
        variation = variations[variation_index % len(variations)]
    else:
        variation = {"angle": "overhead", "focus": "centered", "depth": "sharp focus"}

    # Build the prompt with scene elements + variation
    prompt_parts = [
        # Subject first (Flux 2 best practice)
        f"{item_name} with {item_description}",
        # Realism descriptors (anti-plastic, authentic look)
        scene.get(
            "realism",
            "authentic handmade appearance with natural imperfections, real food texture not CGI or plastic",
        ),
        # Scene elements (consistent for the shop's theme)
        scene.get("background", ""),
        scene.get("lighting", ""),
        scene.get("mood", ""),
        scene.get("props", ""),
        # Variation elements (different for each image)
        variation.get("angle", ""),
        variation.get("focus", ""),
        variation.get("depth", ""),
        # Photography quality (emphasize real, not artificial)
        "editorial food photography, high resolution, appetizing, shot on Canon 5D Mark IV",
    ]

    # Filter empty parts and join
    full_prompt = ", ".join(part for part in prompt_parts if part)

    return {
        "prompt": full_prompt,
        "scene_id": scene_id,
        "scene_name": scene.get("name", scene_id),
        "variation_index": variation_index,
        "variation": variation,
    }


# Replace with fuzzy matching as this approach *sucks* 🤠
def detect_item_type(item_name: str, item_description: str) -> str:
    """Auto-detect the food category based on item name/description."""
    text = f"{item_name} {item_description}".lower()

    if any(word in text for word in ["pizza", "margherita", "pepperoni", "calzone"]):
        return "pizza"
    elif any(
        word in text
        for word in ["pasta", "spaghetti", "penne", "fettuccine", "lasagna", "ravioli"]
    ):
        return "pasta"
    elif any(word in text for word in ["salad", "greens", "caesar", "arugula"]):
        return "salad"
    elif any(
        word in text
        for word in [
            "cake",
            "cookie",
            "brownie",
            "tiramisu",
            "gelato",
            "ice cream",
            "dessert",
            "cannoli",
        ]
    ):
        return "dessert"
    elif any(word in text for word in ["sandwich", "sub", "panini", "wrap", "burger"]):
        return "sandwich"
    elif any(
        word in text
        for word in ["wings", "breadsticks", "appetizer", "bruschetta", "garlic bread"]
    ):
        return "appetizer"
    elif any(
        word in text
        for word in ["soda", "drink", "beer", "wine", "coffee", "tea", "smoothie"]
    ):
        return "drink"
    else:
        return "default"


def build_prompt(
    item_name: str, item_description: str, item_type: str = None, templates: dict = None
) -> str:
    """Build a complete prompt using templates."""
    if templates is None:
        templates = load_templates()

    # Auto-detect type if not provided
    if item_type is None:
        item_type = detect_item_type(item_name, item_description)

    # Get template (fallback to default)
    template = templates.get(item_type, templates.get("default", {}))

    # Build prompt parts
    parts = [
        f"{item_name} with {item_description}",
        template.get("suffix", ""),
        template.get("background", ""),
        template.get("lighting", ""),
        template.get("camera", ""),
        "inviting and delicious mood",
    ]

    # Filter empty parts and join
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

    print(f"Generating with seed {actual_seed}...")
    prompt_id = queue_prompt(updated_workflow)
    wait_for_completion(prompt_id)

    image_path = get_latest_image()
    image_base64 = image_to_base64(image_path)

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

        # DEV MODE: Allow overriding config URLs per-request for testing
        # This lets developers test their own branches without changing the endpoint
        request_scenes_url = job_input.get("scenes_url")
        request_templates_url = job_input.get("templates_url")

        if request_scenes_url:
            print(f"DEV MODE: Using custom scenes_url: {request_scenes_url}")
            SCENES_URL = request_scenes_url
            CONFIG_CACHE.pop("scenes", None)  # Clear cache to force reload

        if request_templates_url:
            print(f"DEV MODE: Using custom templates_url: {request_templates_url}")
            TEMPLATES_URL = request_templates_url
            CONFIG_CACHE.pop("templates", None)  # Clear cache to force reload

        # Load workflow and templates
        workflow = load_workflow()
        templates = load_templates()

        # Get input parameters
        item_name = job_input.get("item_name", "pepperoni pizza")
        item_description = job_input.get("item_description", "classic toppings")
        item_type = job_input.get(
            "item_type"
        )  # Optional, auto-detected if not provided
        num_images = min(
            max(job_input.get("num_images", 1), 1), 4
        )  # Clamp 1-4 (max variations per scene)
        auto_select = job_input.get("auto_select", False)

        # Scene-based generation for consistent shop themes with varied compositions
        scene = job_input.get("scene")  # e.g., "rustic_italian", "modern_minimal", etc.

        # Reference image scene extraction (GPT-4V analyzes image to create scene config)
        reference_image = job_input.get("reference_image")  # Single base64 image
        extract_scene = job_input.get("extract_scene", False)  # Analyze with GPT-4V
        save_scene_as = job_input.get(
            "save_scene_as"
        )  # Optional: name for extracted scene

        # Legacy support for multiple reference images (not actively used)
        reference_images = job_input.get("reference_images", [])

        # Handle reference images (future: integrate with workflow)
        ref_paths = []
        if reference_images:
            print(f"Received {len(reference_images)} reference images")
            ref_paths = save_reference_images(reference_images[:4])

        # Flux 2 doesn't use negative prompts effectively
        negative_prompt = job_input.get("negative_prompt", "")

        # Start ComfyUI if not running
        if comfyui_process is None or comfyui_process.poll() is not None:
            print("Starting ComfyUI server...")
            comfyui_process = start_comfyui_server()
            wait_for_server()

        results = []
        base_seed = job_input.get("seed")
        extracted_scene = None

        # REFERENCE IMAGE MODE: Extract scene + use img2img for visual consistency
        if reference_image and extract_scene:
            print("Extracting scene from reference image using GPT-5.1...")
            try:
                from scene_extractor import (
                    extract_scene_from_image,
                    build_prompt_from_extracted_scene,
                )

                # Step 1: Extract detailed scene characteristics
                extracted_scene = extract_scene_from_image(reference_image)
                print(f"Extracted scene: {extracted_scene.get('name', 'Unknown')}")
                
                # Step 2: Save reference image for img2img workflow
                ref_path = save_reference_for_workflow(reference_image)
                print(f"Reference saved for img2img: {ref_path}")
                
                # Step 3: Load img2img workflow (uses reference as latent starting point)
                img2img_workflow = load_workflow_img2img()
                
                # Get denoise value (higher = more change from reference, lower = more similar)
                denoise = job_input.get("denoise", 0.6)  # Default 0.6 = 60% new, 40% reference
                img2img_workflow["10"]["inputs"]["denoise"] = denoise
                print(f"Using denoise: {denoise} (lower = more similar to reference)")

                # Generate images using extracted scene config + img2img
                for i in range(num_images):
                    prompt_data = build_prompt_from_extracted_scene(
                        item_name, item_description, extracted_scene, i
                    )
                    positive_prompt = prompt_data["prompt"]
                    print(f"Built prompt: {positive_prompt[:200]}...")

                    seed = base_seed if (i == 0 and base_seed is not None) else None

                    print(f"Generating img2img variation {i + 1}/{num_images}")
                    result = generate_single_image(
                        img2img_workflow, positive_prompt, negative_prompt, seed
                    )

                    result["camera_angle"] = prompt_data.get("camera_angle", "")
                    result["variation_index"] = i
                    result["prompt"] = positive_prompt
                    result["denoise"] = denoise
                    results.append(result)

                # Build response with extracted scene info
                response = {
                    "images": results,
                    "extracted_scene": extracted_scene,
                    "scene_name": extracted_scene.get("name", "Custom Style"),
                    "item_type": item_type
                    or detect_item_type(item_name, item_description),
                    "num_images": num_images,
                    "denoise": denoise,
                    "status": "success",
                    "mode": "reference_img2img",
                }

                # Include scene_id if user wants to save it
                if save_scene_as:
                    response["scene_id"] = save_scene_as
                    response["save_scene_as"] = save_scene_as
                    print(f"Scene can be saved as: {save_scene_as}")

            except Exception as e:
                print(f"Scene extraction failed: {e}")
                import traceback

                traceback.print_exc()
                # Fall back to default scene
                scene = "rustic_italian"
                extracted_scene = None

        # SCENE-BASED GENERATION: Different prompts for each image (meaningful variety)
        if not extracted_scene and scene:
            print(f"Using scene: {scene} with {num_images} variations")

            for i in range(num_images):
                # Build unique prompt for each variation
                prompt_data = build_scene_prompt(item_name, item_description, scene, i)
                positive_prompt = prompt_data["prompt"]

                seed = base_seed if (i == 0 and base_seed is not None) else None

                print(
                    f"Generating variation {i + 1}/{num_images}: {prompt_data['variation']}"
                )
                result = generate_single_image(
                    workflow, positive_prompt, negative_prompt, seed
                )

                # Add variation metadata to result
                result["variation"] = prompt_data["variation"]
                result["variation_index"] = i
                result["prompt"] = positive_prompt
                results.append(result)

            # Response includes scene info
            response = {
                "images": results,
                "scene": scene,
                "scene_name": load_scenes().get(scene, {}).get("name", scene),
                "item_type": item_type or detect_item_type(item_name, item_description),
                "num_images": num_images,
                "status": "success",
            }

        # LEGACY MODE: Same prompt, different seeds (for backwards compatibility)
        else:
            positive_prompt = job_input.get("positive_prompt")
            if not positive_prompt:
                positive_prompt = build_prompt(
                    item_name, item_description, item_type, templates
                )

            for i in range(num_images):
                seed = base_seed if (i == 0 and base_seed is not None) else None
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
            }

        # Apply LLM judge if requested (now more useful with varied images!)
        if auto_select and num_images > 1:
            try:
                from llm_judge import judge_images

                images_b64 = [r["image_base64"] for r in results]
                judge_result = judge_images(images_b64, item_name)

                response["judge_result"] = judge_result
                response["best_image"] = results[judge_result["best_index"]]
                response["best_index"] = judge_result["best_index"]

                print(
                    f"LLM Judge selected image {judge_result['best_index'] + 1}: {judge_result.get('reasoning', '')}"
                )
            except Exception as e:
                print(f"LLM Judge failed: {e}")
                response["judge_error"] = str(e)
                response["best_image"] = results[0]
                response["best_index"] = 0
        elif num_images == 1:
            response["best_image"] = results[0]
            response["best_index"] = 0

        # Cleanup reference images
        if ref_paths:
            cleanup_reference_images()
            response["reference_images_used"] = len(ref_paths)

        # Add available scenes to response for discoverability
        response["available_scenes"] = get_available_scenes()

        print(f"Generated {num_images} image(s) successfully")
        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"error": str(e), "status": "failed"}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
