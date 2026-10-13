"""Fixed 4-task-per-episode sequences for the peer-check game, shared by every arm (game k of each arm uses sequence k).

Rules, from the repo's pairing rules (experiments/tasks.py) extended to four workers: the four tasks of an episode
share a task type, are distinct instances, and code tasks never share a spec_key (clean/buggy twins would let a
worker read another's ground truth off its own). No task repeats within a sequence. Each sequence covers the three
task types equally often, in a seeded random order.
"""
import json
import random
from pathlib import Path

from experiments.tasks import _task_pool_by_id, is_code_task_type, task_spec_key, task_type_of

TASK_TYPES = ("code_analysis", "data_search", "record_extraction")


def make_sequences(repo_root: Path, *, n_sequences: int, episodes: int, seed: int) -> list[list[list[str]]]:
    rng = random.Random(seed)
    pool = _task_pool_by_id(repo_root)
    by_type = {t: sorted(i for i, task in pool.items() if task_type_of(task) == t) for t in TASK_TYPES}
    sequences = []
    for _ in range(n_sequences):
        types = [TASK_TYPES[i % 3] for i in range(episodes)]
        rng.shuffle(types)
        used: set[str] = set()
        seq = []
        for t in types:
            candidates = [i for i in by_type[t] if i not in used]
            rng.shuffle(candidates)
            quad, specs = [], set()
            for task_id in candidates:
                spec = task_spec_key(pool[task_id]) if is_code_task_type(t) else ""
                if spec and spec in specs:
                    continue
                quad.append(task_id)
                specs.add(spec)
                if len(quad) == 4:
                    break
            if len(quad) < 4:
                raise ValueError(f"not enough {t} tasks left for a 4-task episode")
            used.update(quad)
            seq.append(quad)
        sequences.append(seq)
    return sequences


def write_sequences(out_dir: Path, sequences: list[list[list[str]]], seed: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, seq in enumerate(sequences, start=1):
        (out_dir / f"seq{k:02d}.json").write_text(json.dumps(
            {"seed": seed, "sequence": k, "episodes": [{"tasks": quad} for quad in seq]}, indent=1))


def read_sequence(path: Path, repo_root: Path) -> list[list[dict]]:
    """Resolve a stored sequence to task dicts (copies), validating the 4-worker rules."""
    pool = _task_pool_by_id(repo_root)
    episodes = []
    seen: set[str] = set()
    for entry in json.loads(path.read_text())["episodes"]:
        ids = [str(i) for i in entry["tasks"]]
        if len(ids) != 4 or len(set(ids)) != 4 or seen & set(ids):
            raise ValueError(f"{path}: bad episode {ids}")
        tasks = [json.loads(json.dumps(pool[i])) for i in ids]
        if len({task_type_of(t) for t in tasks}) != 1:
            raise ValueError(f"{path}: mixed task types in {ids}")
        specs = [task_spec_key(t) for t in tasks if task_spec_key(t)]
        if len(specs) != len(set(specs)):
            raise ValueError(f"{path}: code twins in {ids}")
        seen.update(ids)
        episodes.append(tasks)
    return episodes
