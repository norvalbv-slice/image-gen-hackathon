"""
Model downloader for ComfyUI + Flux 2.0
Downloads required models if not present
"""

import os
import urllib.request
import sys

COMFYUI_PATH = os.environ.get("COMFYUI_PATH", "/comfyui")

MODELS = [
    {
        "name": "Flux 2.0 Dev Q4_K_S (GGUF)",
        "url": "https://huggingface.co/chatpig/flux2-dev-gguf/resolve/main/flux2-dev-Q4_K_S.gguf",
        "path": f"{COMFYUI_PATH}/models/unet/flux2-dev-Q4_K_S.gguf",
        "size_gb": 8.5,
    },
    {
        "name": "CLIP-L",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "path": f"{COMFYUI_PATH}/models/clip/clip_l.safetensors",
        "size_gb": 0.25,
    },
    {
        "name": "T5-XXL FP16",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
        "path": f"{COMFYUI_PATH}/models/clip/t5xxl_fp16.safetensors",
        "size_gb": 9.5,
    },
    {
        "name": "Flux VAE",
        "url": "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors",
        "path": f"{COMFYUI_PATH}/models/vae/ae.safetensors",
        "size_gb": 0.3,
    },
]


def download_file(url: str, dest: str, name: str):
    """Download a file with progress"""
    if os.path.exists(dest):
        print(f"✓ {name} already exists")
        return True

    os.makedirs(os.path.dirname(dest), exist_ok=True)

    print(f"⬇ Downloading {name}...")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print(f"\n✓ {name} downloaded successfully")
        return True
    except Exception as e:
        print(f"\n✗ Failed to download {name}: {e}")
        return False


def progress_hook(count, block_size, total_size):
    """Progress hook for urlretrieve"""
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write(f"\r  Progress: {percent}%")
    sys.stdout.flush()


def download_all_models():
    """Download all required models"""
    print("=" * 50)
    print("ComfyUI + Flux 2.0 Model Downloader")
    print("=" * 50)

    total_size = sum(m["size_gb"] for m in MODELS)
    print(f"\nTotal download size: ~{total_size:.1f} GB")
    print(f"Models directory: {COMFYUI_PATH}/models\n")

    success = True
    for model in MODELS:
        if not download_file(model["url"], model["path"], model["name"]):
            success = False

    print("\n" + "=" * 50)
    if success:
        print("All models downloaded successfully!")
    else:
        print("Some models failed to download. Check errors above.")
    print("=" * 50)

    return success


if __name__ == "__main__":
    success = download_all_models()
    sys.exit(0 if success else 1)
