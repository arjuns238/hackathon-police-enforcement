# 01: Lit review and plan — hackathon-police-enforcement

*2026-10-12, Claude + asri. Phase 0: nothing here commits compute. Take time; pushback welcome.*

## Mission statement

The one narrow, differential question this project answers, and the one sentence a reader should remember.
What is explicitly OUT of scope.

## Contribution ledger

One row per claimed contribution. Verdicts come from the lit scans in `research/`.

| # | contribution | verdict (OPEN / PARTIALLY CLAIMED / CLAIMED) | closest prior work | verified how (full text / abstract only) |
|---|---|---|---|---|
| 1 | Trusted agent (system-prompt-enforced peer) solicits collusion from a group of LLM agents, with per-target logging of accept/reject | PARTIALLY CLAIMED | Zeng & Rudzicz 2605.27593 (environment offers + fixed partner invitation); Shi et al. 2609.24967 App. E.5 (scripted violating peer, one pair) | full text (figures not viewed) |
| 2 | Effect of the offerer's approach style (rapport, incremental vs blunt, authority, reciprocity) on acceptance, offer content held fixed | PARTIALLY CLAIMED | Zeng V0-V5 (offer-text framing only); Colosseum 2602.15198 (authority/reciprocity, but colluders extracting actions); Shi E.5 (content/verdict) | full text (figures not viewed); Meincke / Zeng 2024 persuasion work abstract only |
| 3 | Targets voice suspicion that the offering peer is a plant/test | PARTIALLY CLAIMED (adjacent only; exact claim unmeasured) | General eval awareness (Needham 2505.23836, Apollo, Sonnet 4.5 card); Paglieri 2609.04170 anecdote; Zeng App. A evaluator-mention effect | mostly abstract / snippet; Zeng full text |
| 4 | Targets report a received collusion offer to an overseer (explicit report tool) | PARTIALLY CLAIMED (adjacent only; exact claim unmeasured) | WhistleBench 2511.17085 (human misconduct); Paglieri 2609.04170 (swarm, ~24% whistleblowers); Lee SSRN 7426061 | WhistleBench full text via fetch; others abstract / snippet only |
| 5 | Visible vs undercover enforcement agent compared head to head (plus "one of you might be a plant" arm) | OPEN (≈20 searches) | Agrawal 2507.01413 (announced LLM overseer deters collusion; bundled with punishment; no covert arm); Zeng App. A evaluator cue; overlaps sprint track 3.4 | Agrawal full text; Zeng table; others abstract only |

**Re-verify before citing numerically:**
- Zeng & Rudzicz 2605.27593: per-framing acceptance rates (Table 3 column alignment, e.g. GPT-4.1 V2 = 52), v1 vs v2 differences, and whether the code repo (AgentSafety2025/LLM-Agent-collusion) matches v2.
- Shi et al. 2609.24967: the 13.6% -> 41.2% scripted-peer effect (Gemini-3.1-Flash-Lite, full feedback only) and 93.6% / 66.0%; the Apart page also cites a different "Shi et al." (2607.05132).
- Colosseum 2602.15198: which regret the 2.65x / 2.77x persuasion numbers refer to (figures not viewed).
- Paglieri 2609.04170 (24% whistleblowers, prover-phi anecdote): only press / snippet level.
- Sprint page: the "submission window has closed" string vs the 23-25 Oct dates; and all "no one did X" claims (rerun searches and check other teams' 3.2 submissions just before the sprint).
- Human-literature numbers (Miller 59% / 62%, POP Center, entrapment cases): abstract / secondary only.

## Literature review — key papers (from `research/01_lit_scan_trusted_agents.md`)

1. Zeng & Rudzicz, Voluntary Collusion with Secret Tools (arXiv:2605.27593) [FULL] — closest prior art and the sprint's 3.2 base; offer framings V0-V5, partner invitation, 12 models; offerer is the environment.
2. Shi, Zhang & Yang, Emergent Collusion in Long-Horizon LLM Agent Interaction (arXiv:2609.24967) [FULL] — scripted violating peer moves acceptance 13.6% -> 41.2% (App. E.5); public code with controlled-peer harness.
3. Nakamura et al., Colosseum (arXiv:2602.15198) [FULL] — authority nudge / reciprocity trade taxonomy, regret + judge metrics, reusable code; persuaders are colluders.
4. Tao et al., GroupGuard (arXiv:2603.13940) [FULL] — has a "honeypot" layer, but it is a disposition quiz for already-flagged colluders, not a collusion offer.
5. Greenblatt et al., AI Control (arXiv:2312.06942) [FULL] and Gardner-Challis et al. (arXiv:2602.20628) [FULL, first ~100k chars] — synthetic honeypot inputs to a monitor; plant realism is the main validity threat.
6. Paglieri et al., Emergent Cheating and Whistleblowing in Autonomous Research Swarms (arXiv:2609.04170) [LOW-CONFIDENCE] — only in-swarm evidence on whistleblowing (~24%) and test-inference.
7. Agrawal et al., WhistleBench (arXiv:2511.17085) [FULL via fetch] — reporting is model-, prompt- and tool-dependent; needs an explicit report tool and both model groups.
8. Agrawal et al., Evaluating LLM Agent Collusion in Double Auctions (arXiv:2507.01413) [ABS] — low-setup-risk testbed with seller messaging, overseer and authority pressure.
9. Petri (Anthropic; MIT, Inspect) + Cullen multi-agent extension [LOW-CONFIDENCE] — scaffolding for an LLM auditor acting as a peer among N targets.
10. Garra, Mitigating Emergent Collusion in LLM Pricing Agents (arXiv:2609.13037) [ABS] — inserted active entrant is the strongest mitigation; closest economics analogue to inserting a controlled agent.
11. Meincke et al., Call Me A Jerk (SSRN 5357179) [ABS] and Zeng et al., PAP (arXiv:2401.06373) [ABS] — persuasion-principle taxonomy and effect sizes (human-to-LLM only).
12. Spagnolo 2004 (CEPR DP 4840) and Bigoni et al. 2012 (RAND) [ABS] — leniency / trust-destruction theory and lab evidence; source of the known-sting-policy and reporting-incentive arms.

## Instrument requirements

What must be true of our measurement tools before any result is believed (e.g. a probe generalises across
topics; a steering direction is causal, not just readable), and the check for each.

## Registered predictions

- **P-1 (short name).** Prediction with a threshold. Confidence + one line of reasoning.

## Scope options

For anything that could grow: **tethered** (kept, tied to the main question) / **stretch** (only if time) / **cut**.

## Risk register

| risk | how we would notice | what we do then |
|---|---|---|
| … | … | … |

## Compute plan

Model(s), hardware, rough GPU hours and cost per phase. Flag any step-change spend for asri before it happens.
