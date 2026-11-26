"""Cost-cutting experiment: does a cheaper web-search setting hurt the rate agent?

Runs the real rate agent on the same 3 Art Shopee contracts with search_context_size
low / medium / high and records tokens, searches, cost and answer quality.
Run from the project root:  .venv/bin/python report/experiments/search_context_experiment.py
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.capabilities import WebSearch  # noqa: E402

from app import agents, config  # noqa: E402
from app.harness import GUARDRAIL_INSTRUCTIONS, fence  # noqa: E402

CONTRACTS = [
    dict(id=1, name="Point of Sale & Payment Services Agreement", counterparty="Square, Inc.", line_type="expense",
         category="Software / SaaS", annual_value=2280, start_date="2025-12-16", end_date="2026-12-15", auto_renew=True,
         scope="In-store POS software (Square for Retail Plus, 2 registers), card readers, inventory tracking; $190/month plus 2.6% + $0.15 per in-person transaction."),
    dict(id=2, name="Email & SMS Marketing Agreement", counterparty="Klaviyo, Inc.", line_type="expense",
         category="Software / SaaS", annual_value=1800, start_date="2026-01-01", end_date="2026-12-31", auto_renew=True,
         scope="Email newsletters, SMS campaigns and abandoned-cart flows for up to 5,000 profiles; $150/month."),
    dict(id=3, name="Wholesale Purchasing Agreement", counterparty="Jerry's Artarama, Inc.", line_type="expense",
         category="Inventory & Supplies", annual_value=22000, start_date="2025-12-06", end_date="2026-12-05", auto_renew=True,
         scope="Wholesale acrylic and oil paints, brushes, canvas, sketchbooks; 35% off list with $22,000 annual minimum."),
]


async def run_one(size: str, c: dict) -> dict:
    from app.harness import _measure
    block, _ = fence("contract_scope", c["scope"], 2000)
    prompt = (f"Business type: Retail & E-commerce\nContract: {agents._contract_brief(c)}\n"
              f"Scope (untrusted):\n{block}\n\nSearch the web for current market rates and recommend.")
    a = Agent(agents._model(), output_type=agents.RateRecommendation,
              capabilities=[WebSearch(search_context_size=size)],
              instructions=RATE_INSTRUCTIONS, retries=2)
    r = await a.run(prompt)
    m = _measure(r)
    out = agents.clean_text(r.output.model_dump())
    return {"size": size, "contract": c["counterparty"], **m,
            "recommendation": out["recommendation"], "confidence": out["confidence"],
            "impact": out["estimated_annual_impact"], "has_market_range": out["market_low"] is not None,
            "alternatives": len(out["alternatives"]), "alternatives_with_url": sum(1 for x in out["alternatives"] if x["url"])}


RATE_INSTRUCTIONS = (
    "You are a procurement analyst for small businesses. Use web search to find current, "
    "real market pricing for the product or service in the contract and compare it to what "
    "the business pays (expense line) or charges (revenue line). For expense contracts, find "
    "cheaper or better-value providers and estimate yearly savings. For revenue contracts "
    "(e.g. client service agreements), check whether the business is under-pricing versus the "
    "market and estimate the yearly uplift from a price increase at renewal. Cite provider "
    "URLs when you have them. Be conservative: if evidence is thin, say so and use low confidence."
    + GUARDRAIL_INSTRUCTIONS
)


async def main():
    rows = []
    for size in ("low", "medium", "high"):
        results = await asyncio.gather(*(run_one(size, c) for c in CONTRACTS))
        rows.extend(results)
        for r in results:
            print(json.dumps(r))
    out = Path(__file__).with_name("search_context_results.json")
    out.write_text(json.dumps(rows, indent=2))
    print("saved", out)


if __name__ == "__main__":
    asyncio.run(main())
