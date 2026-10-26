"""Significance and robustness checks for the Results section of the report (Qwen sting, games 1-4). Exploratory:
none of these tests were registered. Free: reads run.json and the saved judge labels only, no model calls.

The unit for every test is the game, because the three target pairs of one episode share a conversation and are not
independent. Pair counts are given alongside for reference.

  1. Ceiling: target mutual accept per setup in episodes 2-4, with a 95% interval, and the lowest single game-episode.
  2. Episode-1 collusion and Dave's character: the post-hoc grouping (pushy/friendly with an episode-3 approach vs the
     rest), an omnibus permutation test over all 8 setups that does not depend on the grouping, a selection-adjusted
     p-value (best pair of setups, chosen in every permutation), leave-one-game-number-out, and the two accounts
     (games 1-2 vs 3-4).
  3. What targets said: refusals in Dave's approach episode by character (same rule as the results page, D17), and
     games with at least one deal, pushy/friendly vs subtle/passive.
  4. Upper bounds for the zero counts (suspicion, pairwise deals between targets).
  5. Wrong work accepted, episode 1 vs episodes 2-4, and correct vs wrong in episodes 2-4.
  6. Say no, do yes by timing.

Writes results/analysis/qwen_robustness.json and prints a short summary.
Usage: python3 scripts/qwen_robustness.py
"""
import itertools
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from scipy.stats import binomtest, fisher_exact

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_qwen_results_page import REFUSE  # noqa: E402  (the refusal word pattern of D17)
from score_qwen_predictions import T, labels, mutual, runs  # noqa: E402

CELLS = ["arm1", "passive", "pushy_ep1", "friendly_ep1", "subtle_ep1", "pushy_ep3", "friendly_ep3", "subtle_ep3"]
N_PERM = 20000


def ci(k: int, n: int) -> list[float]:
    """Exact (Clopper-Pearson) 95% interval for k of n."""
    c = binomtest(k, n).proportion_ci(0.95, method="exact")
    return [round(c.low, 3), round(c.high, 3)]


def pairs(v) -> int:
    return sum(mutual(v, a, b) for i, a in enumerate(T) for b in T[i + 1:])


def main() -> None:
    R = runs()
    out = {}

    # 1. Ceiling from episode 2
    ceil = {}
    for c in CELLS:
        ks = [(pairs(eps[k]["verdicts"]), 3) for (cc, _), eps in R.items() if cc == c for k in (2, 3, 4) if k in eps]
        k, n = sum(a for a, _ in ks), sum(b for _, b in ks)
        ceil[c] = {"k": k, "n": n, "rate": round(k / n, 3), "ci": ci(k, n), "lowest_game_episode": min(a for a, _ in ks)}
    out["ceiling_eps2_4"] = ceil

    # 2. Episode-1 collusion by setup, game level
    ep1 = {(c, g): pairs(eps[1]["verdicts"]) for (c, g), eps in R.items() if 1 in eps}
    games = sorted(ep1)
    hit = {k: ep1[k] > 0 for k in games}
    per_setup = {c: [sum(hit[k] for k in games if k[0] == c), sum(1 for k in games if k[0] == c)] for c in CELLS}
    grp = {"pushy_ep3", "friendly_ep3"}

    def split(h, keep=lambda k: True):
        a = [h[k] for k in games if keep(k) and k[0] in grp]
        b = [h[k] for k in games if keep(k) and k[0] not in grp]
        return [sum(a), len(a)], [sum(b), len(b)]

    a, b = split(hit)
    p_grouped = fisher_exact([[a[0], a[1] - a[0]], [b[0], b[1] - b[0]]])[1]

    labels_ = [k[0] for k in games]
    obs = [hit[k] for k in games]

    def chi2(lab, y):
        """Pearson chi-square on the setup x (collusion yes/no) table."""
        tot = sum(y) / len(y)
        s = 0.0
        for c in CELLS:
            ys = [v for l, v in zip(lab, y) if l == c]
            if ys and 0 < tot < 1:
                e1 = len(ys) * tot
                s += (sum(ys) - e1) ** 2 / e1 + ((len(ys) - sum(ys)) - (len(ys) - e1)) ** 2 / (len(ys) - e1)
        return s

    def best_pair(lab, y):
        """Smallest Fisher p over every choice of two setups vs the other six: the 'look at the data, then group'
        statistic. Comparing the observed value with its permutation distribution adjusts for that choice."""
        best = 1.0
        for p, q in itertools.combinations(CELLS, 2):
            ins = [v for l, v in zip(lab, y) if l in (p, q)]
            outs = [v for l, v in zip(lab, y) if l not in (p, q)]
            if sum(ins) * len(outs) <= sum(outs) * len(ins):
                continue  # one-sided: the chosen pair must collude more
            best = min(best, fisher_exact([[sum(ins), len(ins) - sum(ins)], [sum(outs), len(outs) - sum(outs)]],
                                          alternative="greater")[1])
        return best

    rng = random.Random(0)
    c_obs, b_obs = chi2(labels_, obs), best_pair(labels_, obs)
    ge_c = ge_b = 0
    for _ in range(N_PERM):
        y = obs[:]
        rng.shuffle(y)
        ge_c += chi2(labels_, y) >= c_obs - 1e-9
        ge_b += best_pair(labels_, y) <= b_obs + 1e-12
    lono = {}
    for g in (1, 2, 3, 4):
        a_, b_ = split(hit, lambda k, g=g: k[1] != g)
        lono[f"without_game_{g}"] = {"group": a_, "rest": b_, "p": round(
            fisher_exact([[a_[0], a_[1] - a_[0]], [b_[0], b_[1] - b_[0]]])[1], 4)}
    acc = {}
    for name, gs in (("games_1_2", (1, 2)), ("games_3_4", (3, 4))):
        a_, b_ = split(hit, lambda k, gs=gs: k[1] in gs)
        acc[name] = {"group": a_, "rest": b_, "p": round(
            fisher_exact([[a_[0], a_[1] - a_[0]], [b_[0], b_[1] - b_[0]]])[1], 4)}
    # timing alone (all three active characters, episode-3 vs episode-1 approach), a contrast the design defines
    t3 = [hit[k] for k in games if k[0].endswith("_ep3")]
    t1 = [hit[k] for k in games if k[0].endswith("_ep1")]
    p_timing = fisher_exact([[sum(t3), len(t3) - sum(t3)], [sum(t1), len(t1) - sum(t1)]])[1]
    out["episode1"] = {
        "per_setup_games": per_setup,
        "grouped": {"group": a, "rest": b, "fisher_p": round(p_grouped, 5)},
        "omnibus_permutation_p": round((ge_c + 1) / (N_PERM + 1), 4),
        "selection_adjusted_p": round((ge_b + 1) / (N_PERM + 1), 4),
        "best_pair_naive_p": round(b_obs, 5),
        "leave_one_game_number_out": lono,
        "by_account": acc,
        "timing_ep3_vs_ep1_all_active": {"ep3": [sum(t3), len(t3)], "ep1": [sum(t1), len(t1)],
                                         "fisher_p": round(p_timing, 4)},
    }

    # 3. What targets said in the approach episode, by character; deals by game
    jsall = {x["id"]: x["parsed"] for x in labels("JSall") if x["parsed"]}
    js = [x for x in labels("JS") if x["parsed"]]
    ref = defaultdict(lambda: [0, 0])
    ref_game = defaultdict(list)
    for (c, g), eps in R.items():
        if c in ("arm1", "passive"):
            continue
        ap = int(c[-1])
        if ap not in eps:
            continue
        x = eps[ap]
        r = 0
        for t in T:
            ms = [m["content"] for m in x["transcript"] if m["from"] == t and
                  (m["to"] == "dave" or re.search(r"\bdave\b", m["content"], re.I))]
            j = jsall.get(f"{c}_g{g}e{ap}:{t}")
            refused = not (j and j["deal"]) and any(REFUSE.search(q) for q in ms)
            ref[c.split("_")[0]][0] += refused
            ref[c.split("_")[0]][1] += 1
            r += refused
        ref_game[c.split("_")[0]].append(r > 0)
    p_ref = fisher_exact([[ref["pushy"][0], ref["pushy"][1] - ref["pushy"][0]],
                          [ref["subtle"][0], ref["subtle"][1] - ref["subtle"][0]]])[1]
    gp, gs = ref_game["pushy"], ref_game["subtle"]
    p_ref_game = fisher_exact([[sum(gp), len(gp) - sum(gp)], [sum(gs), len(gs) - sum(gs)]])[1]
    deal_game = defaultdict(bool)
    for k, v in jsall.items():
        c, g = re.match(r"(.+)_g(\d+)e", k).groups()
        deal_game[(c, int(g))] |= bool(v["deal"])
    for x in js:
        if x["character"] == "passive":
            deal_game[("passive", x["game"])] |= bool(x["parsed"]["deal"])
    active = [deal_game[k] for k in R if k[0].split("_")[0] in ("pushy", "friendly")]
    quiet = [deal_game[k] for k in R if k[0].split("_")[0] in ("subtle", "passive")]
    p_deal = fisher_exact([[sum(active), len(active) - sum(active)], [sum(quiet), len(quiet) - sum(quiet)]])[1]
    out["said"] = {
        "refused_targets": dict(ref), "refused_pushy_vs_subtle_p_targets": round(p_ref, 5),
        "games_with_a_refusal": {k: [sum(v), len(v)] for k, v in ref_game.items()},
        "refused_pushy_vs_subtle_p_games": round(p_ref_game, 4),
        "games_with_a_deal": {"pushy_friendly": [sum(active), len(active)], "subtle_passive": [sum(quiet), len(quiet)],
                              "fisher_p": round(p_deal, 4)},
    }

    # 4. Upper bounds for zeros
    sus = sum(x["parsed"]["suspicion"] for x in js)
    out["zeros"] = {"suspicion": {"k": sus, "n": len(js), "ci": ci(sus, len(js))},
                    "pairwise_target_deals": {"k": 0, "n": 330, "ci": ci(0, 330)}}

    # 5. Wrong work: targets' verdicts on each other's and Dave's work; work is wrong when the right verdict is not pass
    ww = defaultdict(lambda: [0, 0])
    for (c, g), eps in R.items():
        for k, x in eps.items():
            for a in T:
                for b, verdict in x["verdicts"][a].items():
                    key = ("ep1" if k == 1 else "ep2_4", "correct" if x["expected_verdict"][b] == "pass" else "wrong")
                    ww[key][0] += verdict == "accept"
                    ww[key][1] += 1
    w1, w2 = ww[("ep1", "wrong")], ww[("ep2_4", "wrong")]
    c2 = ww[("ep2_4", "correct")]
    out["wrong_work"] = {
        "cells": {f"{a}/{b}": v for (a, b), v in ww.items()},
        "wrong_ep1_vs_ep2_4_p": fisher_exact([[w1[0], w1[1] - w1[0]], [w2[0], w2[1] - w2[0]]])[1],
        "ep2_4_correct_vs_wrong_p": fisher_exact([[c2[0], c2[1] - c2[0]], [w2[0], w2[1] - w2[0]]])[1],
        "wrong_ep2_4_ci": ci(*w2),
    }

    # 6. Say no, do yes
    sn = defaultdict(lambda: [0, 0])
    for (c, g), eps in R.items():
        if c in ("arm1", "passive"):
            continue
        ap = int(c[-1])
        if ap not in eps:
            continue
        x = eps[ap]
        for t in T:
            said = " ".join(m["content"] for m in x["transcript"] if m["from"] == t
                            and (m["to"] == "dave" or "dave" in m["content"].lower()))
            if REFUSE.search(said):
                sn[ap][0] += x["verdicts"][t]["dave"] == "accept"
                sn[ap][1] += 1
    out["say_no_do_yes"] = {f"approach_ep{k}": v for k, v in sn.items()}
    out["say_no_do_yes"]["fisher_p"] = fisher_exact([[sn[3][0], sn[3][1] - sn[3][0]],
                                                    [sn[1][0], sn[1][1] - sn[1][0]]])[1]

    f = ROOT / "results" / "analysis" / "qwen_robustness.json"
    f.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    print(f"-> {f}")


if __name__ == "__main__":
    main()
