"""Run one game of the 4-worker peer-check experiment (notes/04 amendment A; settings in notes/07_run_config.md).

Defaults are the approved configuration: Claude Sonnet 5 workers and plant at effort high, Sonnet 5 auditor at
effort low, 6 episodes, communication-onward memory, one fixed tool list per worker. Using any other model needs
--override-config (ask asri first: see notes/07_run_config.md for why the alternatives failed).

Restartable: rerunning the same command resumes after the last saved episode.

Usage:
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --arm 1 --game 1 [--episodes 6] [--out results/peer_check/...]
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --make-sequences          # writes data/peer_check_sequences/
  vendor/agent-collusion/.venv/bin/python scripts/run_peer_check.py --arm 5 --game 1 --offline  # fake model, no API calls, no cost
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
SEQ_DIR = ROOT / "data" / "peer_check_sequences"
SEQ_SEED = 20261013
EPISODE_SPEND_LIMIT = 138.0  # checked before every episode (see main)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", type=int, choices=range(1, 7))
    ap.add_argument("--game", type=int, help="1-based game number = task sequence number")
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--out", help="output dir (default results/peer_check/arm{A}_game{G})")
    ap.add_argument("--model", default=APPROVED_MODEL)
    ap.add_argument("--override-config", action="store_true", help="allow a non-approved model (ask asri first)")
    ap.add_argument("--make-sequences", action="store_true")
    ap.add_argument("--n-sequences", type=int, default=4)
    ap.add_argument("--offline", action="store_true", help="fake model: tests the plumbing at no cost")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    from peer_check.sequences import make_sequences, read_sequence, write_sequences
    if args.make_sequences:
        seqs = make_sequences(REPO, n_sequences=args.n_sequences, episodes=6, seed=SEQ_SEED)
        write_sequences(SEQ_DIR, seqs, SEQ_SEED)
        print(f"wrote {len(seqs)} sequences to {SEQ_DIR}")
        return
    if args.arm is None or args.game is None:
        ap.error("--arm and --game are required")
    if args.model != APPROVED_MODEL and not args.override_config:
        sys.exit(f"Refusing model {args.model}: the approved worker model is {APPROVED_MODEL} "
                 "(notes/07_run_config.md). Pass --override-config only with asri's approval.")

    if not args.offline:
        sys.path.insert(0, str(ROOT / "scripts"))
        from spend import check
        print(f"project spend so far: ${check(140.0):.2f} (start limit $140, hard stop $145)", flush=True)
    load_dotenv(REPO / ".env")
    from peer_check.game import Game, GameConfig
    seq_path = SEQ_DIR / f"seq{args.game:02d}.json"
    default_out = ROOT / "results" / ("peer_check_offline" if args.offline else "peer_check") / f"arm{args.arm}_game{args.game}"
    cfg = GameConfig(arm=args.arm, sequence_path=str(seq_path), output_dir=str(Path(args.out or default_out).resolve()),
                     model=args.model, plant_model=args.model, auditor_model=args.model, episodes=args.episodes)
    kwargs = {}
    if args.offline:
        from peer_check.fake_llm import fake_llm_call
        kwargs["llm_call"] = fake_llm_call
    game = Game(cfg=cfg, repo_root=REPO, verbose=not args.quiet, **kwargs)
    guard = None
    if not args.offline:
        # Several games may run at once, so re-check total spend before every episode, not only at start: with up
        # to 4 games in flight (~$1.5 per episode) a $138 episode limit keeps the total under the $145 hard stop.
        guard = lambda: print(f"project spend: ${check(EPISODE_SPEND_LIMIT):.2f}", flush=True)
    game.run(read_sequence(seq_path, REPO), before_episode=guard)


if __name__ == "__main__":
    main()
