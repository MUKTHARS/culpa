"""Run AgentDispute-150 against Culpa and baselines. Writes bench/results.json and bench/results.md.

Systems:
  claim_keywords    baseline: classify from the buyer's claim text alone (what a naive dispute bot does)
  culpa_no_replay   Culpa without the agent-replay check
  culpa_full        all four checks + the settlement policy (rule-based, no LLM)
  culpa_full_llm    culpa_full with the Gemini judge/clarifier (only with --llm; costs API credits)

Usage: python bench/run.py [--llm]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "apps" / "api"))

from engine.pipeline import analyze  # noqa: E402
from engine.policy import decide  # noqa: E402
from engine.types import FAULT_CLASSES, CaseBundle  # noqa: E402

DATA = ROOT / "data" / "agentdispute-150.jsonl"
CANONICAL_SPLIT = {
    "F1": {"buyer": 0.0, "merchant": 0.0, "agent_provider": 1.0},
    "F2": {"buyer": 0.0, "merchant": 0.0, "agent_provider": 1.0},
    "F3": {"buyer": 0.6, "merchant": 0.0, "agent_provider": 0.4},
    "F4": {"buyer": 0.0, "merchant": 1.0, "agent_provider": 0.0},
    "F5": {"buyer": 0.0, "merchant": 1.0, "agent_provider": 0.0},
    "F6": {"buyer": 1.0, "merchant": 0.0, "agent_provider": 0.0},
}
GOLD_BEARER = {"F1": "agent_provider", "F2": "agent_provider", "F3": "split", "F4": "merchant", "F5": "merchant",
               "F6": "buyer"}

KEYWORDS = [
    ("F5", ("never arrived", "not received", "nothing was delivered", "never got", "can't even find")),
    ("F1", ("spending", "limit", "allowed", "authorized", "approved spending")),
    ("F4", ("not as described", "different from the listing", "listing said", "scam")),
    ("F3", ("i wanted",)),
    ("F2", ("agent", "bot", "i asked for", "wrong")),
]


def keyword_classify(claim: str) -> str:
    text = claim.lower()
    for label, words in KEYWORDS:
        if any(w in text for w in words):
            return label
    return "F6"


def bearer(action: str, liability: dict) -> str | None:
    if action == "review":
        return None
    if action == "contest":
        return "buyer"
    if action == "refund_partial":
        return "split"
    return next(iter(liability), None)


def run_system(name: str, rows: list[dict], llm=None) -> dict:
    preds = []
    t0 = time.perf_counter()
    for r in rows:
        b = CaseBundle.from_dict(r["bundle"])
        if name == "claim_keywords":
            fc = keyword_classify(b.claim.text)
            action, _, liability = decide(fc, CANONICAL_SPLIT[fc], 1.0, b.order.amount)
            preds.append({"id": r["id"], "pred": fc, "action": action, "bearer": bearer(action, liability)})
            continue
        v = analyze(b, llm=llm, use_replay=(name != "culpa_no_replay"))
        preds.append({"id": r["id"], "pred": v.fault_class, "action": v.action, "bearer": bearer(v.action, v.liability),
                      "confidence": v.confidence})
    elapsed = time.perf_counter() - t0
    return {"name": name, "metrics": metrics(rows, preds), "ms_per_case": round(1000 * elapsed / len(rows), 3),
            "predictions": preds}


def metrics(rows: list[dict], preds: list[dict]) -> dict:
    n = len(rows)
    gold = [r["label"] for r in rows]
    pred = [p["pred"] for p in preds]
    correct = sum(g == p for g, p in zip(gold, pred, strict=True))

    f1s = []
    for c in FAULT_CLASSES:
        tp = sum(g == c and p == c for g, p in zip(gold, pred, strict=True))
        fp = sum(g != c and p == c for g, p in zip(gold, pred, strict=True))
        fn = sum(g == c and p != c for g, p in zip(gold, pred, strict=True))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)

    escalated = [p["action"] == "review" for p in preds]
    wrong_money = sum(not esc and p["bearer"] != GOLD_BEARER[g]
                      for g, p, esc in zip(gold, preds, escalated, strict=True))
    auto = [(g, p["pred"]) for g, p, esc in zip(gold, preds, escalated, strict=True) if not esc]
    non_f6 = [p for g, p in zip(gold, pred, strict=True) if g != "F6"]
    f6_gold = [p for g, p in zip(gold, pred, strict=True) if g == "F6"]

    confusion: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    for g, p in zip(gold, pred, strict=True):
        confusion[g][p or "none"] += 1

    by_hard = {}
    for flag in (False, True):
        idx = [i for i, r in enumerate(rows) if r["hard"] == flag]
        if idx:
            by_hard["hard" if flag else "standard"] = round(sum(gold[i] == pred[i] for i in idx) / len(idx), 3)

    return {
        "n": n,
        "accuracy": round(correct / n, 3),
        "macro_f1": round(sum(f1s) / len(f1s), 3),
        "wrong_money_rate": round(wrong_money / n, 3),
        "escalation_rate": round(sum(escalated) / n, 3),
        "auto_decided_accuracy": round(sum(g == p for g, p in auto) / len(auto), 3) if auto else None,
        "friendly_fraud_recall": round(sum(p == "F6" for p in f6_gold) / len(f6_gold), 3) if f6_gold else None,
        "false_accusation_rate": round(sum(p == "F6" for p in non_f6) / len(non_f6), 3) if non_f6 else None,
        "accuracy_by_difficulty": by_hard,
        "confusion": {g: dict(confusion[g]) for g in FAULT_CLASSES},
    }


def write_markdown(results: dict, path: Path) -> None:
    lines = [
        "# AgentDispute-150 results",
        "",
        f"Generated {results['generated_at']}. {results['n_cases']} cases, 25 per fault class, "
        f"{results['n_hard']} hard. Labels are true by construction (see `bench/generate.py`).",
        "",
        "| System | Accuracy | Macro-F1 | Wrong-money rate | Escalated | Auto-decided accuracy | "
        "Friendly-fraud recall | False-accusation rate | ms/case |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in results["systems"]:
        m = s["metrics"]
        lines.append(f"| {s['name']} | {m['accuracy']:.1%} | {m['macro_f1']:.3f} | {m['wrong_money_rate']:.1%} | "
                     f"{m['escalation_rate']:.1%} | {m['auto_decided_accuracy'] if m['auto_decided_accuracy'] is not None else '-'} | "
                     f"{m['friendly_fraud_recall']} | {m['false_accusation_rate']} | {s['ms_per_case']} |")
    lines += ["", "Wrong-money rate: share of all cases where money would move to the wrong party "
                  "(escalated cases move no money).", "",
              "Limitations: the data is synthetic and the engine was designed around the same fault taxonomy, so "
              "these numbers measure in-distribution behaviour, not real-world accuracy. Hard cases use misleading "
              "claim text, formatting noise and repeat-disputer signals.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run culpa_full_llm (uses GEMINI_API_KEY and its quota)")
    args = ap.parse_args()

    if not DATA.exists():
        from generate import main as gen_main

        gen_main()
    rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]

    systems = [run_system(n, rows) for n in ("claim_keywords", "culpa_no_replay", "culpa_full")]
    if args.llm:
        from services.llm_service import get_llm

        llm = get_llm()
        if llm is None:
            print("GEMINI_API_KEY not set; skipping culpa_full_llm")
        else:
            systems.append(run_system("culpa_full_llm", rows, llm=llm))

    results = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_cases": len(rows),
        "n_hard": sum(r["hard"] for r in rows),
        "systems": systems,
    }
    (ROOT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_markdown(results, ROOT / "results.md")
    for s in systems:
        m = s["metrics"]
        print(f"{s['name']:16} acc={m['accuracy']:.3f} f1={m['macro_f1']:.3f} wrong_money={m['wrong_money_rate']:.3f} "
              f"escalated={m['escalation_rate']:.3f}")


if __name__ == "__main__":
    main()
