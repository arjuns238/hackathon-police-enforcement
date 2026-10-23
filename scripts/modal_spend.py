"""Modal spend for the Qwen sting (notes/12): asri's $50 of Modal credits, dashboard budget $50, our soft stop $45.

Reads Modal's billing report for the workspace since 2026-10-22 (the day the Modal work started). Uses the Modal
client installed as a uv tool (~/.local/share/uv/tools/modal), so the game's venv does not need Modal.

Usage: python3 scripts/modal_spend.py            # prints the total
       from modal_spend import check; check(45)  # exits if spend is at or above the limit
"""
import subprocess
import sys
from pathlib import Path

MODAL_PY = Path.home() / ".local/share/uv/tools/modal/bin/python"
SOFT_STOP = 45.0
_REPORT = """
import datetime as dt, warnings
warnings.simplefilter("ignore")
import modal
start = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc)
try:
    rows = modal.Workspace.from_context().billing.report(start=start, resolution="d")
except Exception:
    rows = modal.billing.workspace_billing_report(start=start, resolution="d")
print(sum(float(r["cost"] if isinstance(r, dict) else r.cost) for r in rows))
"""


def modal_spend() -> float:
    out = subprocess.run([str(MODAL_PY), "-c", _REPORT], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        sys.exit(f"Could not read Modal spend; refusing to start.\n{out.stderr[-800:]}")
    return float(out.stdout.strip().splitlines()[-1])


def check(limit: float = SOFT_STOP) -> float:
    spent = modal_spend()
    if spent >= limit:
        sys.exit(f"Refusing to start: Modal spend is ${spent:.2f}, at or above the ${limit:.0f} soft stop "
                 "(credits $50). Ask asri.")
    return spent


if __name__ == "__main__":
    print(f"Modal spend since 2026-10-22: ${modal_spend():.2f} (soft stop ${SOFT_STOP:.0f}, credits $50)")
