"""Serve Qwen-3.8-27B (BF16) with vLLM on one Modal A100 80 GB, as an OpenAI-compatible endpoint for the Qwen sting
games (notes/12). Paid from asri's Modal credits (dashboard budget $50; our soft stop $45, scripts/modal_spend.py).

  ~/.local/bin/modal deploy modal_gpu/serve_qwen.py      # prints the URL; the game uses <URL>/v1
  ~/.local/bin/modal app stop qwen-sting                  # stop it for good (it also stops itself when idle)

Auth: vLLM requires the key in the Modal secret `qwen-sting-key` (variable QWEN_API_KEY); the same key is in .env
as QWEN_API_KEY (gitignored). Never print it.

Cost controls: at most one container; it shuts down after 5 idle minutes (the next request starts it again, ~5 min
cold start); weights are cached on a Volume, so the 56 GB download happens once.

Requests longer than 150 s come back as a 303 redirect from Modal's proxy; LiteLLM's OpenAI client follows
redirects (up to 20, about 50 minutes), which the smoke test checks.
"""
import os
import subprocess

import modal

MODEL = "Qwen/Qwen3.8-27B"
REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"  # pinned 2026-10-22
SERVED_NAME = "qwen3.8-27b"  # the game calls it as openai/qwen3.8-27b, the paper's model string
VLLM_VERSION = "0.31.0"
GPU = "A100-80GB"
PORT = 8000
MINUTES = 60

image = modal.Image.debian_slim(python_version="3.12").uv_pip_install(f"vllm=={VLLM_VERSION}")
hf_cache = modal.Volume.from_name("qwen-sting-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("qwen-sting-vllm-cache", create_if_missing=True)

# QWEN_APP_NAME=qwen-sting-2 deploys an identical second server (its own GPU and URL) for a second wave of games.
app = modal.App(os.environ.get("QWEN_APP_NAME", "qwen-sting"))


@app.function(
    image=image,
    gpu=GPU,
    cpu=4,
    memory=16384,  # MiB requested; billed on the larger of request and use
    max_containers=1,
    scaledown_window=5 * MINUTES,
    timeout=24 * 60 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("qwen-sting-key")],
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=PORT, startup_timeout=30 * MINUTES)
def serve() -> None:
    cmd = [
        "vllm", "serve", MODEL,
        "--revision", REVISION,
        "--served-model-name", SERVED_NAME,
        "--host", "0.0.0.0", "--port", str(PORT),
        "--api-key", os.environ["QWEN_API_KEY"],
        "--max-model-len", "131072",
        "--gpu-memory-utilization", "0.92",
        "--enable-prefix-caching",
        "--reasoning-parser", "qwen3",
        "--enable-auto-tool-choice", "--tool-call-parser", "qwen3_coder",
        "--limit-mm-per-prompt", '{"image": 0, "video": 0}',  # text only: skip the vision encoder's memory
    ]
    # FlashInfer's top-k/top-p sampler compiles a kernel at start-up and needs nvcc, which this image lacks (first
    # boot 2026-10-24 died with "Could not find nvcc"); vLLM's own sampler needs no compiler.
    subprocess.Popen(cmd, env={**os.environ, "VLLM_USE_FLASHINFER_SAMPLER": "0"})
