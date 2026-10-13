# pod/ — LEGACY: rented GPU pods (RunPod), superseded by `azure/` on 2026-10-03

Kept for reference and as a fallback if a project ever needs a GPU that Azure will not give us (H100, multi-GPU
nodes). **New projects use `azure/` — see `azure/README.md`.** Nothing in this folder is run by the Azure path
except `requirements-pod.txt` (baked into the image) and `smoke_test.py` (run as a job).

How the pod way worked, in one paragraph: rent a pod (one A100 80 GB, RunPod secure cloud, ~$1.59/h), SSH in
as root, `/workspace` is the volume that survives a stop. `pod/remote_setup.sh <host> <port>` pushes the repo and
runs `pod_setup.sh` (Jupyter + interp stack, HF cache on the volume) and `pod/post_setup.sh` (fixes re-applied
after every restart) on the pod; `connect.sh <host> <port>` tunnels `localhost:8888` so the Jupyter MCP can
drive notebooks; `pod/bootstrap.sh` pulls the model and datasets onto the volume; `pod/push.sh` /
`pod/pull_results.sh` move code and results over SSH; `pod/deadman_stop.sh` auto-stops the pod after a batch.
`pod/config.sh` holds the project folder on the pod (`/workspace/<project>`), the same path the Azure share is
mounted at, which is why notebooks and scripts did not have to change.

Why we left: the pod billed while idle (three incidents of forgotten/duplicated GPU time), every restart
re-installed the stack, and Azure credits could not be spent on GPU VMs at all — but they can be spent on
serverless A100 containers. The full story is in `TEMPLATE.md`.
