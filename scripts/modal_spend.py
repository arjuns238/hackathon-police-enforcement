"""Modal spend for the Qwen sting (notes/12). asri's account: $50 of credits, dashboard budget $50, soft stop $45.

Reads Modal's billing report for the workspace since MODAL_SPEND_SINCE (default 2026-10-22, the day asri's Modal work
started). A teammate on their own account sets MODAL_SOFT_STOP and MODAL_SPEND_SINCE in .env (see RUNBOOK_QWEN.md). Uses the Modal
client installed as a uv tool (~/.local/share/uv/tools/modal), so the game's venv does not need Modal.

The billing report is a daily aggregate and can trail real use by hours, so it is also printed with the GPU
containers running right now. The dashboard budget ($50) is the real-time backstop.

Usage: python3 scripts/modal_spend.py                 # prints the total and running containers
       from modal_spend import check; check(45)       # exits if spend is at or above the limit
       check(45, strict=False)                        # before an episode: a failed read warns instead of exiting
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _env(name: str, default: str) -> str:
    """From the environment, else from the project's .env (this script also runs under a bare python3)."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default

# The Modal client installed with `uv tool install modal` (RUNBOOK_QWEN.md); MODAL_PYTHON / MODAL_CLI override.
MODAL_PY = Path(_env("MODAL_PYTHON", str(Path.home() / ".local/share/uv/tools/modal/bin/python")))
MODAL_CLI = Path(_env("MODAL_CLI", shutil.which("modal") or str(Path.home() / ".local/bin/modal")))
SOFT_STOP = float(_env("MODAL_SOFT_STOP", "45"))
SINCE = _env("MODAL_SPEND_SINCE", "2026-10-22")  # YYYY-MM-DD, UTC
_REPORT = """
import datetime as dt, sys, warnings
warnings.simplefilter("ignore")
import modal
start = dt.datetime.fromisoformat(sys.argv[1]).replace(tzinfo=dt.timezone.utc)
try:
    rows = modal.Workspace.from_context().billing.report(start=start, resolution="d")
except Exception:
    rows = modal.billing.workspace_billing_report(start=start, resolution="d")
print(sum(float(r["cost"] if isinstance(r, dict) else r.cost) for r in rows))
"""


def _read_billing() -> float:
    out = subprocess.run([str(MODAL_PY), "-c", _REPORT, SINCE], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[-800:])
    return float(out.stdout.strip().splitlines()[-1])


def modal_spend(strict: bool = True) -> float | None:
    """Billed Modal spend; one retry. On a second failure: exit if strict, else warn and return None."""
    for attempt in (1, 2):
        try:
            return _read_billing()
        except Exception as e:  # noqa: BLE001 - any failure to read is handled the same way
            err = e
    if strict:
        sys.exit(f"Could not read Modal spend; refusing to start.\n{err}")
    print(f"WARNING: could not read Modal spend ({str(err)[-200:]}); continuing, the $50 dashboard budget still "
          "applies", flush=True)
    return None


def running_containers() -> int | None:
    """GPU containers running now (any app), from `modal container list --json`; None if it cannot be read."""
    try:
        out = subprocess.run([str(MODAL_CLI), "container", "list", "--json"], capture_output=True, text=True,
                             timeout=60)
        return len(json.loads(out.stdout or "[]"))
    except Exception:  # noqa: BLE001
        return None


def check(limit: float = SOFT_STOP, strict: bool = True) -> float | None:
    spent = modal_spend(strict=strict)
    if spent is not None and spent >= limit:
        sys.exit(f"Refusing to start: Modal spend is ${spent:.2f}, at or above the ${limit:.0f} soft stop "
                 "(MODAL_SOFT_STOP). Ask asri.")
    return spent


def describe(spent: float | None) -> str:
    n = running_containers()
    billed = "unreadable" if spent is None else f"${spent:.2f}"
    return (f"Modal billed since {SINCE}: {billed} (can lag by hours); containers running now: "
            f"{'?' if n is None else n}; soft stop ${SOFT_STOP:.0f}")


if __name__ == "__main__":
    print(describe(modal_spend()))
