# AgentDispute-150 results

Generated 2026-11-02T05:03:28Z. 150 cases, 25 per fault class, 30 hard. Labels are true by construction (see `bench/generate.py`).

| System | Accuracy | Macro-F1 | Wrong-money rate | Escalated | Auto-decided accuracy | Friendly-fraud recall | False-accusation rate | ms/case |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claim_keywords | 73.3% | 0.698 | 26.7% | 0.0% | 0.733 | 0.0 | 0.08 | 0.154 |
| culpa_no_replay | 65.3% | 0.660 | 0.0% | 34.7% | 1.0 | 1.0 | 0.0 | 0.539 |
| culpa_full | 98.7% | 0.993 | 0.0% | 2.7% | 1.0 | 1.0 | 0.0 | 0.705 |

Wrong-money rate: share of all cases where money would move to the wrong party (escalated cases move no money).

Limitations: the data is synthetic and the engine was designed around the same fault taxonomy, so these numbers measure in-distribution behaviour, not real-world accuracy. Hard cases use misleading claim text, formatting noise and repeat-disputer signals.
