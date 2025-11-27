"""
RunPod Serverless Handler for ComfyUI + Flux 2.0 (Slim Version)
Models downloaded on first run using huggingface_hub (cached by FlashBoot)
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
from huggingface_hub import hf_hub_download

# Configuration
COMFYUI_PATH = os.environ.get("COMFYUI_PATH", "/comfyui")
WORKFLOW_PATH = "/workflow.json"
OUTPUT_DIR = f"{COMFYUI_PATH}/output"
COMFYUI_PORT = 8188

# Model paths within ComfyUI (matching where loaders expect files)
DIFFUSION_PATH = f"{COMFYUI_PATH}/models/diffusion_models"
VAE_PATH = f"{COMFYUI_PATH}/models/vae"
TEXT_ENCODER_PATH = f"{COMFYUI_PATH}/models/text_encoders"


def ensure_models_downloaded():
    """Download official FP8 models using huggingface_hub"""
    import shutil

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


def update_workflow_prompt(workflow, positive_prompt, negative_prompt=None, seed=None):
    if "6" in workflow:
        workflow["6"]["inputs"]["text"] = positive_prompt
    if negative_prompt and "7" in workflow:
        workflow["7"]["inputs"]["text"] = negative_prompt
    if "10" in workflow:
        workflow["10"]["inputs"]["seed"] = (
            seed if seed else random.randint(0, 2**32 - 1)
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


comfyui_process = None
initialized = False


def handler(event):
    global comfyui_process, initialized

    try:
        if not initialized:
            print("Initializing - downloading models if needed...")
            ensure_models_downloaded()
            initialized = True

        job_input = event.get("input", {})

        # Load workflow to get prompt template
        workflow = load_workflow()

        positive_prompt = job_input.get("positive_prompt")
        if not positive_prompt:
            # Get template from workflow.json and substitute placeholders
            prompt_template = workflow["6"]["inputs"]["text"]
            item_name = job_input.get("item_name", "pepperoni pizza")
            item_description = job_input.get("item_description", "classic toppings")
            positive_prompt = prompt_template.format(
                item_name=item_name, item_description=item_description
            )

        # Flux 2 doesn't use negative prompts effectively - use empty string
        negative_prompt = job_input.get("negative_prompt", "")

        seed = job_input.get("seed")

        if comfyui_process is None or comfyui_process.poll() is not None:
            print("Starting ComfyUI server...")
            comfyui_process = start_comfyui_server()
            wait_for_server()

        cleanup_outputs()
        workflow = update_workflow_prompt(
            workflow, positive_prompt, negative_prompt, seed
        )
        actual_seed = workflow["10"]["inputs"]["seed"]

        print(f"Queuing prompt with seed {actual_seed}...")
        prompt_id = queue_prompt(workflow)

        print("Waiting for generation...")
        wait_for_completion(prompt_id)

        image_path = get_latest_image()
        image_base64 = image_to_base64(image_path)

        print(f"Image generated: {image_path}")
        return {
            "image_base64": image_base64,
            "seed": actual_seed,
            "prompt": positive_prompt,
            "status": "success",
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"error": str(e), "status": "failed"}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
