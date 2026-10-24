"""Run one game of the 4-worker peer-check experiment (notes/04 amendment A; settings in notes/07_run_config.md).

Defaults are the approved configuration: Claude Sonnet 5 workers and plant at effort high, Sonnet 5 auditor at
effort low, 6 episodes, communication-onward memory, one fixed tool list per worker. Using any other model needs
--override-config (ask asri first: see notes/07_run_config.md for why the alternatives failed).

Restartable: rerunning the same command resumes after the last saved episode.

Usage:
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --arm 1 --game 1 [--episodes 6] [--out results/peer_check/...]
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --make-sequences          # writes data/peer_check_sequences/
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --arm 5 --game 1 --offline  # fake model, no API calls, no cost

Qwen sting (notes/12): workers and Dave are Qwen-3.8-27B on the Modal server (modal_gpu/serve_qwen.py); needs
QWEN_API_KEY and QWEN_BASE_URL (".../v1") in .env. Arm 1 = baseline; arms 11-14 = direct / hint / benign / give-first.
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --model openai/qwen3.8-27b --arm 11 --offer-episode 1 --episodes 2 --game 1
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "vendor" / "agent-collusion"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT / "src"))
os.chdir(REPO)

from dotenv import load_dotenv  # noqa: E402

APPROVED_MODEL = "anthropic/claude-sonnet-5"
# asri approved Qwen-3.8 for the sting on 2026-10-22 (notes/12). "default" sends no reasoning_effort: the Qwen chat
# template then uses its default, xhigh (the paper's setting); "high" would make the template raise.
APPROVED_MODELS = {APPROVED_MODEL: {"effort": "high", "tool_choice": "auto"},
                   "openai/qwen3.8-27b": {"effort": "medium", "tool_choice": "required"}}  # medium: asri 2026-10-24 (paper: xhigh)
STING_STYLE = {11: "direct", 12: "hint", 13: "benign", 14: "givefirst"}
QWEN_REQUEST_TIMEOUT = 1800  # seconds; a stuck turn cannot hold the GPU for longer
SEQ_DIR = ROOT / "data" / "peer_check_sequences"
SEQ_SEED = 20261013
EPISODE_SPEND_LIMIT = 138.0  # checked before every episode (see main)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", type=int, choices=[*range(1, 8), *STING_STYLE])
    ap.add_argument("--offer-episode", type=int, default=2, help="1-based episode of the scripted offer (sting: 1 or 3)")
    ap.add_argument("--tool-choice", choices=["auto", "required"], help="default: the approved model's setting")
    ap.add_argument("--game", type=int, help="1-based game number = task sequence number")
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--out", help="output dir (default results/peer_check/arm{A}_game{G})")
    ap.add_argument("--model", default=APPROVED_MODEL)
    ap.add_argument("--override-config", action="store_true", help="allow a non-approved model (ask asri first)")
    ap.add_argument("--make-sequences", action="store_true")
    ap.add_argument("--n-sequences", type=int, default=4)
    ap.add_argument("--offline", action="store_true", help="fake model: tests the plumbing at no cost")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--episode-limit", type=float, default=EPISODE_SPEND_LIMIT,
                    help="stop before an episode once project spend reaches this (default $138, set for 4 parallel games; a single game may use up to $142, staying under the $145 hard stop)")
    args = ap.parse_args()

    from peer_check.sequences import make_sequences, read_sequence, write_sequences
    if args.make_sequences:
        seqs = make_sequences(REPO, n_sequences=args.n_sequences, episodes=6, seed=SEQ_SEED)
        write_sequences(SEQ_DIR, seqs, SEQ_SEED)
        print(f"wrote {len(seqs)} sequences to {SEQ_DIR}")
        return
    if args.arm is None or args.game is None:
        ap.error("--arm and --game are required")
    if args.model not in APPROVED_MODELS and not args.override_config:
        sys.exit(f"Refusing model {args.model}: the approved worker models are {', '.join(APPROVED_MODELS)} "
                 "(notes/07_run_config.md, notes/12). Pass --override-config only with asri's approval.")
    settings = APPROVED_MODELS.get(args.model, APPROVED_MODELS[APPROVED_MODEL])
    qwen = args.model.startswith("openai/qwen")

    sys.path.insert(0, str(ROOT / "scripts"))
    if not args.offline and not qwen:
        from spend import check
        print(f"project spend so far: ${check(140.0):.2f} (start limit $140, hard stop $145)", flush=True)
    if not args.offline and qwen:
        from modal_spend import SOFT_STOP, check as modal_check, describe
        print(describe(modal_check(SOFT_STOP)), flush=True)
    # The Sonnet games always ran with this set (run_main_games.sh); keep the environment the same for every game.
    os.environ.setdefault("PEERCHECK_FIXED_TOOLS", "1")
    load_dotenv(REPO / ".env")
    if qwen and not args.offline:
        import litellm
        for var in ("QWEN_API_KEY", "QWEN_BASE_URL"):
            if not os.environ.get(var):
                sys.exit(f"{var} is missing from .env (see modal_gpu/serve_qwen.py)")
        os.environ["OPENAI_API_KEY"] = os.environ["QWEN_API_KEY"]
        os.environ["OPENAI_BASE_URL"] = os.environ["OPENAI_API_BASE"] = os.environ["QWEN_BASE_URL"]
        litellm.request_timeout = QWEN_REQUEST_TIMEOUT
    from peer_check.game import Game, GameConfig
    seq_path = SEQ_DIR / f"seq{args.game:02d}.json"
    default_out = ROOT / "results" / ("peer_check_offline" if args.offline else "peer_check") / f"arm{args.arm}_game{args.game}"
    if qwen:
        cell = f"{STING_STYLE[args.arm]}_ep{args.offer_episode}" if args.arm in STING_STYLE else f"arm{args.arm}"
        default_out = ROOT / "results" / ("qwen_sting_offline" if args.offline else "qwen_sting") / f"{cell}_game{args.game}"
    # A relative --out is relative to the project root, not to the vendored repo this script chdirs into (2026-10-18:
    # a relative --out once sent four games to vendor/agent-collusion/results/, outside spend.py's view).
    out_dir = Path(args.out) if args.out else default_out
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    cfg = GameConfig(arm=args.arm, sequence_path=str(seq_path), output_dir=str(out_dir.resolve()),
                     model=args.model, plant_model=args.model, auditor_model=args.model, episodes=args.episodes,
                     effort=settings["effort"], tool_choice=args.tool_choice or settings["tool_choice"],
                     offer_episode=args.offer_episode)
    kwargs = {}
    if args.offline:
        from peer_check.fake_llm import fake_llm_call
        kwargs["llm_call"] = fake_llm_call
    game = Game(cfg=cfg, repo_root=REPO, verbose=not args.quiet, **kwargs)
    guard = None
    if not args.offline and qwen:
        # Before each episode a failed billing read warns instead of exiting, so a transient Modal API error cannot
        # stop several parallel games at once; the $50 dashboard budget is the real-time backstop.
        guard = lambda: print(describe(modal_check(SOFT_STOP, strict=False)), flush=True)
    elif not args.offline:
        # Several games may run at once, so re-check total spend before every episode, not only at start: with up
        # to 4 games in flight (~$1.5 per episode) a $138 episode limit keeps the total under the $145 hard stop.
        if args.episode_limit > 142.0:
            sys.exit("--episode-limit above $142 would risk the $145 hard stop; ask asri.")
        guard = lambda: print(f"project spend: ${check(args.episode_limit):.2f}", flush=True)
    game.run(read_sequence(seq_path, REPO), before_episode=guard)


if __name__ == "__main__":
    main()
