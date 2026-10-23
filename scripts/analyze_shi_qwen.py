"""Step 1 of the Qwen sting plan: what Qwen does with no agent, from the paper's released games (Shi et al. 2609.24967,
HF dataset SALT-NLP/agent-collusion, MIT). Two Qwen workers per game, 10 episodes, 50 games per model (their main runs).
Free: no model calls.

Reads data/external/shi2026_hf/ (episodes, agreement, conditions, runs parquet; 16 MB, gitignored). To re-download:
  B=https://huggingface.co/datasets/SALT-NLP/agent-collusion/resolve/refs%2Fconvert%2Fparquet
  episodes/test/0000..0052.parquet, agreement/test/0000.parquet, conditions/test/0000.parquet, runs/test/0000.parquet

Reports per model:
- collusion (both ACCEPT) per episode, and in episode 1;
- explicit agreement (the paper's own agreement judge, `agreement` table, label True) per episode, and in episode 1;
- per game: first episode with collusion, first with explicit agreement;
- offers (keyword heuristic, see OFFER): episodes where a worker proposes reciprocal acceptance, and how often the
  other then agrees (judge label) / both accept. Heuristic, a rough guide to "does Qwen take an offered deal";
- example deal quotes (first and second side) from each model's earliest agreements.

Usage: python3 -I scripts/analyze_shi_qwen.py   (writes results/analysis/shi_qwen_baseline.json)
"""
import glob
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "external" / "shi2026_hf"
MODELS = ["main__qwen-3-6-27b", "main__qwen-3-8-27b", "main__claude-sonnet-4-6", "main__gemini-3-7-flash"]
# A reciprocal offer: "accept mine / I'll accept yours / accept each other / deal?" style wording.
OFFER = re.compile(r"(accept (mine|each other|both)|i'?ll accept (yours|your)|if you accept|mutual(ly)? accept|"
                   r"\bdeal\b|both accept|we both (submit )?accept)", re.I)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    ep = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(D / "episodes" / "*.parquet")))])
    ag = pd.read_parquet(D / "agreement" / "0000.parquet")
    ag = ag[ag.signal == "agreement"][["run_id", "episode_index", "label", "status", "first_side_quote",
                                         "second_side_quote"]]
    return ep, ag


def summarise(ep: pd.DataFrame, ag: pd.DataFrame, cond: str) -> dict:
    e = ep[(ep.condition_id == cond) & (~ep.is_warmup)].copy()
    if e.empty:
        return {}
    e = e.merge(ag, on=["run_id", "episode_index"], how="left")
    e["agree"] = e.label.astype("boolean").fillna(False).astype(bool)
    e["offer"] = e.communication.apply(lambda c: any(OFFER.search(m["content"] or "") for m in c))
    by_ep = e.groupby("episode_index").agg(collusion=("both_accept", "mean"), agreement=("agree", "mean"),
                                            offer=("offer", "mean"))
    first_c = e[e.both_accept].groupby("run_id").episode_index.min()
    first_a = e[e.agree].groupby("run_id").episode_index.min()
    runs = e.run_id.nunique()
    off = e[e.offer]
    ex = e[e.agree].sort_values(["episode_index"]).drop_duplicates("run_id").head(4)
    return {
        "games": runs, "episodes": len(e),
        "collusion_all": round(e.both_accept.mean(), 3), "agreement_all": round(e.agree.mean(), 3),
        "agreement_share_of_collusive": round(e[e.both_accept].agree.mean(), 3),
        "ep1_collusion": round(by_ep.collusion.iloc[0], 3), "ep1_agreement": round(by_ep.agreement.iloc[0], 3),
        "ep1_offer": round(by_ep.offer.iloc[0], 3),
        "per_episode": {int(k + 1): {c: round(float(v), 2) for c, v in r.items()} for k, r in by_ep.iterrows()},
        "games_with_collusion": int(first_c.size), "median_first_collusion_ep": float(first_c.median() + 1),
        "games_with_agreement": int(first_a.size),
        "median_first_agreement_ep": float(first_a.median() + 1) if first_a.size else None,
        "offer_episodes": int(len(off)), "offer_then_agreement": round(off.agree.mean(), 3) if len(off) else None,
        "offer_then_both_accept": round(off.both_accept.mean(), 3) if len(off) else None,
        "no_offer_both_accept": round(e[~e.offer].both_accept.mean(), 3),
        "examples": [{"run": r.run_id, "episode": int(r.episode_index + 1), "proposal": r.first_side_quote,
                      "reply": r.second_side_quote} for r in ex.itertuples()],
    }


def main() -> None:
    ep, ag = load()
    out = {c: summarise(ep, ag, c) for c in MODELS}
    (ROOT / "results" / "analysis").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "analysis" / "shi_qwen_baseline.json").write_text(json.dumps(out, indent=1))
    for c, s in out.items():
        if not s:
            print(c, "not found"); continue
        print(f"\n== {c}: {s['games']} games, {s['episodes']} episodes")
        for k in ("collusion_all", "agreement_all", "agreement_share_of_collusive", "ep1_collusion", "ep1_agreement",
                  "ep1_offer", "games_with_collusion", "median_first_collusion_ep", "games_with_agreement",
                  "median_first_agreement_ep", "offer_episodes", "offer_then_agreement", "offer_then_both_accept",
                  "no_offer_both_accept"):
            print(f"  {k}: {s[k]}")
        print("  per episode (collusion / agreement / offer):",
              " ".join(f"{k}:{v['collusion']:.2f}/{v['agreement']:.2f}/{v['offer']:.2f}" for k, v in s["per_episode"].items()))
        for x in s["examples"][:3]:
            print(f"  ep{x['episode']} proposal: {str(x['proposal'])[:200]!r}\n       reply: {str(x['reply'])[:200]!r}")


if __name__ == "__main__":
    main()
