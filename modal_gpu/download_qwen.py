"""Fetch the Qwen-3.8-27B weights into the Modal Volume on a CPU container, so the GPU never bills for the download
(notes/12). Its own app because Modal refuses a whole app that holds an A100 function until the account has a
payment method; this one has no GPU. Image and Volume are defined exactly as in serve_qwen.py (same image, cached).

  ~/.local/bin/modal run modal_gpu/download_qwen.py
"""
import modal

MODEL = "Qwen/Qwen3.8-27B"
REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"  # same pin as serve_qwen.py
VLLM_VERSION = "0.31.0"

image = modal.Image.debian_slim(python_version="3.12").uv_pip_install(f"vllm=={VLLM_VERSION}")
hf_cache = modal.Volume.from_name("qwen-sting-hf-cache", create_if_missing=True)

app = modal.App("qwen-sting-download")


@app.function(image=image, cpu=4, memory=8192, timeout=90 * 60, volumes={"/root/.cache/huggingface": hf_cache})
def download() -> None:
    from huggingface_hub import snapshot_download
    path = snapshot_download(MODEL, revision=REVISION)
    hf_cache.commit()
    print("weights at", path)
