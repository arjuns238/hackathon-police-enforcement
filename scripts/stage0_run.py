"""Stage 0 of notes/03_registered_plan_market.md: does talking raise prices in a 5-seller, 3-buyer market?

Runs the Agrawal et al. double auction (vendored, patched, in vendor/llm-agent-collusion) with Claude sellers
and buyers, in two arms: no seller messaging vs public seller messaging. Restartable: sessions whose
session.json is complete are skipped; partial session folders are deleted and re-run.

Smoke test:  .venv/bin/python scripts/stage0_run.py --n 1 --rounds 3 --out results/stage0_smoke
Full run:    .venv/bin/python scripts/stage0_run.py --n 10 --workers 5
Config B:    .venv/bin/python scripts/stage0_run.py --n 10 --workers 5 --buyers 2 --out results/stage0_B
"""
import argparse
import json
import os
import random
import shutil
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "llm-agent-collusion"
sys.path.insert(0, str(VENDOR))
os.chdir(VENDOR)  # the vendored code loads its prompt templates by relative path

from src.continuous_double_auction.cda_types import ExperimentParams  # noqa: E402
from src.continuous_double_auction.identities import (  # noqa: E402
    get_random_agent_names, get_random_buyer_company_names, get_random_seller_company_names)
from src.continuous_double_auction.market.agents import LMBuyer, LMSeller  # noqa: E402
from src.continuous_double_auction.market.market import Market  # noqa: E402
from src.continuous_double_auction.util.logging_util import ExperimentLogger  # noqa: E402
from src.continuous_double_auction.util.misc import get_client, initialize_market  # noqa: E402
from src.resources.model_wrappers import get_usage, reset_usage  # noqa: E402

ARMS = {
    "no_msg": {"seller_comms_enabled": False},
    "msg": {"seller_comms_enabled": True},
}
# $ per million tokens (input, output); used only to print an estimate.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}
N_SELLERS = 5
SELLER_COST, BUYER_VALUE = 80.0, 100.0


def load_env_file(path: Path) -> None:
    """Put KEY=VALUE lines from .env into the environment (without overriding what is already set)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def dollars(usage: dict) -> float:
    total = 0.0
    for model, counts in usage.items():
        price_in, price_out = PRICES.get(model, (0.0, 0.0))
        total += counts["input_tokens"] / 1e6 * price_in + counts["output_tokens"] / 1e6 * price_out
    return total


def _fake_generate(self, messages):
    """--dry-run stand-in for AnthropicClient.generate: random asks/bids, no API call, no cost."""
    return json.dumps({"reflection": "dry run", "plan_for_this_hour": "dry run", "new_memory": "dry run",
                       "scratch_pad_update": "dry run", "ask": round(random.uniform(82, 98), 2),
                       "bid": round(random.uniform(80, 96), 2), "message_to_sellers": "dry run message"})


def run_session(arm: str, idx: int, cfg: dict) -> dict:
    if cfg.get("dry_run"):
        from src.resources import model_wrappers
        model_wrappers.AnthropicClient.generate = _fake_generate
    out = Path(cfg["out"])
    session_dir = out / arm / f"s{idx:02d}"
    session_file = session_dir / "session.json"
    if session_file.exists() and json.loads(session_file.read_text()).get("complete"):
        return {"arm": arm, "idx": idx, "status": "skipped"}
    if session_dir.exists():
        shutil.rmtree(session_dir)

    # Same seed for the same session index in every arm: same names, companies and opening orders.
    random.seed(1000 + idx)
    np.random.seed(1000 + idx)
    model = cfg["model"]
    N_BUYERS = cfg["buyers"]
    params = ExperimentParams(
        seller_valuations=[SELLER_COST] * N_SELLERS,
        buyer_valuations=[BUYER_VALUE] * N_BUYERS,
        seller_models=[model] * N_SELLERS,
        buyer_models=[model] * N_BUYERS,
        rounds=cfg["rounds"],
        tag=f"stage0-{arm}-s{idx:02d}",
        **ARMS[arm],
    )
    logger = ExperimentLogger(params, experiment_id=f"{arm}/s{idx:02d}", base_dir=str(out))
    client_kwargs = {"effort": cfg["effort"], "max_tokens": cfg["max_tokens"]}

    names = get_random_agent_names(N_BUYERS + N_SELLERS)
    buyer_names, seller_names = names[:N_BUYERS], names[N_BUYERS:]
    buyer_companies = get_random_buyer_company_names(N_BUYERS)
    seller_companies = get_random_seller_company_names(N_SELLERS)
    buyers = [LMBuyer(id=f"Buyer {buyer_names[i]}", company=buyer_companies[i], valuation=BUYER_VALUE,
                      expt_params=params, logger=logger,
                      client=get_client(model=model, temperature=params.temperature, **client_kwargs))
              for i in range(N_BUYERS)]
    sellers = [LMSeller(id=f"Seller {seller_names[i]}", company=seller_companies[i], valuation=SELLER_COST,
                        expt_params=params, logger=logger,
                        client=get_client(model=model, temperature=params.temperature, **client_kwargs))
               for i in range(N_SELLERS)]
    logger.metadata["buyer_ids"] = [b.id for b in buyers]
    logger.metadata["seller_ids"] = [s.id for s in sellers]

    # n_claude_agents=0 gives one thread per agent; the SDK backs off on rate limits.
    market = Market(sellers=sellers, buyers=buyers, overseer=None, n_claude_agents=0)
    asks, bids = initialize_market(
        num_sellers=N_SELLERS, seller_ask_center=params.initial_seller_ask_center,
        seller_ask_spread=params.initial_seller_ask_spread, num_buyers=N_BUYERS,
        buyer_bid_center=params.initial_buyer_bid_center, buyer_bid_spread=params.initial_buyer_bid_spread)
    market.set_initial_orders([(asks[i], s.id) for i, s in enumerate(sellers)],
                              [(bids[i], b.id) for i, b in enumerate(buyers)])

    reset_usage()
    start = time.time()
    try:
        for _ in range(params.rounds):
            market.run_round()
            logger.log_auction_round(last_round=market.rounds[-1])
    except Exception:
        # Keep what the failed session spent and why it stopped (refusals, cut-offs, API errors).
        usage = get_usage()
        (session_dir / "error.txt").write_text(
            f"failed in round {len(market.rounds) + 1}\nusage: {json.dumps(usage)}\n\n{traceback.format_exc()}")
        return {"arm": arm, "idx": idx, "status": "failed", "usage": usage,
                "error": traceback.format_exc().splitlines()[-1]}
    logger.save_experiment_summary()

    usage = get_usage()
    record = {
        "complete": True,
        "arm": arm,
        "idx": idx,
        "model": model,
        "effort": cfg["effort"],
        "params": params.model_dump(),
        "seller_ids": logger.metadata["seller_ids"],
        "buyer_ids": logger.metadata["buyer_ids"],
        "rounds": [r.model_dump() for r in market.rounds],
        "usage": usage,
        "est_dollars": round(dollars(usage), 4),
        "seconds": round(time.time() - start, 1),
    }
    session_file.write_text(json.dumps(record, indent=1))
    return {"arm": arm, "idx": idx, "status": "done", "usage": usage, "seconds": record["seconds"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    parser.add_argument("--n", type=int, default=10, help="sessions per arm")
    parser.add_argument("--start", type=int, default=0, help="first session index")
    parser.add_argument("--model", default="claude-haiku-5-5", choices=list(PRICES))
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high"])
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--buyers", type=int, default=3, help="Config A = 3, Config B = 2")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--workers", type=int, default=2, help="sessions run at the same time")
    parser.add_argument("--out", default="results/stage0")
    parser.add_argument("--dry-run", action="store_true", help="fake model replies; tests the plumbing for free")
    args = parser.parse_args()

    load_env_file(ROOT / ".env")
    if not args.dry_run and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No ANTHROPIC_API_KEY found (environment or .env). Add it to .env first.")

    cfg = {"model": args.model, "effort": args.effort, "rounds": args.rounds, "max_tokens": args.max_tokens,
           "buyers": args.buyers,
           "out": str((ROOT / args.out).resolve()), "dry_run": args.dry_run}
    Path(cfg["out"]).mkdir(parents=True, exist_ok=True)
    tasks = [(arm, idx) for idx in range(args.start, args.start + args.n) for arm in args.arms]
    print(f"{len(tasks)} sessions ({args.model}, effort={args.effort}, {args.rounds} rounds, "
          f"{N_SELLERS} sellers, {args.buyers} buyers) -> {cfg['out']}", flush=True)

    total_usage: dict = {}
    failures = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_session, arm, idx, cfg): (arm, idx) for arm, idx in tasks}
        for future in as_completed(futures):
            result = future.result()
            for model, counts in result.get("usage", {}).items():
                agg = total_usage.setdefault(model, {k: 0 for k in counts})
                for k, v in counts.items():
                    agg[k] += v
            if result["status"] == "failed":
                failures += 1
            extra = f" {result['seconds']}s" if "seconds" in result else ""
            extra += f" ERROR: {result['error']}" if "error" in result else ""
            print(f"[{result['arm']} s{result['idx']:02d}] {result['status']}{extra}  "
                  f"running cost ~${dollars(total_usage):.2f}", flush=True)

    print(json.dumps({"usage": total_usage, "est_dollars": round(dollars(total_usage), 4), "failures": failures},
                     indent=1))
    print("BATCH DONE")


if __name__ == "__main__":
    main()
