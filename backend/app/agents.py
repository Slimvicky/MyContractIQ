"""Pydantic AI agents for MyContractIQ.

1. Rate agent       — searches the web for better market rates for a contract.
2. Portfolio agent  — reviews all contracts together for redundancy and consolidation savings.
3. Extraction agent — reads an uploaded contract PDF and fills in the contract fields.

Each agent has a deterministic fallback so the app stays usable without an API key;
fallback results are clearly labelled with source="heuristic".
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from functools import lru_cache
from typing import Literal, Optional

from pydantic import BaseModel, Field

from . import config
from .harness import GUARDRAIL_INSTRUCTIONS, HarnessError, fence, run_agent

# ---------------------------------------------------------------- output models


class Alternative(BaseModel):
    provider: str
    estimated_annual_cost: Optional[float] = Field(None, description="USD per year")
    notes: str = ""
    url: Optional[str] = None


class RateRecommendation(BaseModel):
    summary: str = Field(description="2-3 sentence plain-English summary for a small business owner")
    recommendation: Literal["switch", "renegotiate", "renew", "raise_price", "hold"]
    confidence: Literal["low", "medium", "high"]
    market_low: Optional[float] = Field(None, description="Low end of market annual price, USD")
    market_high: Optional[float] = Field(None, description="High end of market annual price, USD")
    estimated_annual_impact: float = Field(
        0, description="Expense: estimated yearly savings. Revenue: estimated yearly uplift. USD, >= 0"
    )
    alternatives: list[Alternative] = Field(default_factory=list, max_length=5)
    next_steps: list[str] = Field(default_factory=list, max_length=5)


class Finding(BaseModel):
    title: str
    finding_type: Literal["redundancy", "consolidation", "scale_leverage", "underpriced_revenue", "risk"]
    contract_ids: list[int]
    estimated_annual_savings: float = 0
    rationale: str
    recommended_action: str
    priority: Literal["high", "medium", "low"]


class PortfolioReview(BaseModel):
    headline: str
    total_estimated_savings: float = 0
    findings: list[Finding] = Field(default_factory=list)


class ContractExtraction(BaseModel):
    name: Optional[str] = None
    counterparty: Optional[str] = None
    line_type: Optional[Literal["expense", "revenue"]] = Field(
        None, description="revenue if the business is paid (e.g. client service agreement), expense if it pays"
    )
    category: Optional[str] = None
    annual_value: Optional[float] = Field(None, description="Annualised contract value in USD")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notice_days: Optional[int] = None
    auto_renew: Optional[bool] = None
    scope: Optional[str] = Field(None, description="One or two sentence description of what the contract covers")


# ---------------------------------------------------------------- agent factories


@lru_cache
def _model():
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIResponsesModel(config.OPENAI_MODEL, provider=OpenAIProvider(api_key=config.OPENAI_API_KEY))


@lru_cache
def rate_agent():
    from pydantic_ai import Agent
    from pydantic_ai.capabilities import WebSearch

    return Agent(
        _model(),
        output_type=RateRecommendation,
        capabilities=[WebSearch(search_context_size="medium", max_uses=5)],
        instructions=(
            "You are a procurement analyst for small businesses. Use web search to find current, "
            "real market pricing for the product or service in the contract and compare it to what "
            "the business pays (expense line) or charges (revenue line). For expense contracts, find "
            "cheaper or better-value providers and estimate yearly savings. For revenue contracts "
            "(e.g. client service agreements), check whether the business is under-pricing versus the "
            "market and estimate the yearly uplift from a price increase at renewal. Cite provider "
            "URLs when you have them. Be conservative: if evidence is thin, say so and use low confidence."
            + GUARDRAIL_INSTRUCTIONS
        ),
        retries=2,
    )


@lru_cache
def portfolio_agent():
    from pydantic_ai import Agent

    return Agent(
        _model(),
        output_type=PortfolioReview,
        instructions=(
            "You are a portfolio analyst. A small business manages all its contracts in one place. "
            "Find savings that would normally be missed when contracts sit in silos: overlapping scope "
            "(two tools doing the same job), duplicate vendors, contracts that could be consolidated for "
            "volume discounts, scale mismatches (paying for more seats/capacity than needed), and "
            "under-priced revenue contracts. Only reference contract ids that exist in the data. "
            "Give realistic USD savings estimates and concrete next actions."
            + GUARDRAIL_INSTRUCTIONS
        ),
        retries=2,
    )


@lru_cache
def extraction_agent():
    from pydantic_ai import Agent

    return Agent(
        _model(),
        output_type=ContractExtraction,
        instructions=(
            "Extract contract terms from the document text. Leave a field null if it is not stated. "
            "annual_value must be annualised (e.g. $500/month -> 6000)."
            + GUARDRAIL_INSTRUCTIONS
        ),
        retries=2,
    )


# ---------------------------------------------------------------- public helpers


def _contract_brief(c: dict) -> str:
    return (
        f"id={c['id']} | {c['line_type'].upper()} | {c['name']} | counterparty: {c['counterparty']} | "
        f"category: {c['category']} | annual value: ${c['annual_value']:,.0f} | "
        f"term: {c.get('start_date') or '?'} to {c.get('end_date') or '?'} | auto-renew: {bool(c.get('auto_renew'))}"
    )


async def check_rates(contract: dict, business_type: str, user_id: int, trigger: str) -> tuple[dict, str]:
    if not config.ai_enabled():
        return _heuristic_rates(contract).model_dump(), "heuristic"
    scope_block, flags = fence("contract_scope", contract.get("scope") or contract.get("notes") or "", 2000)
    prompt = (
        f"Business type: {business_type}\nContract: {_contract_brief(contract)}\n"
        f"Scope (untrusted):\n{scope_block}\n\nSearch the web for current market rates and recommend."
    )
    try:
        out = await run_agent(rate_agent(), prompt, name="rate_agent", user_id=user_id, trigger=trigger, injection_flags=flags)
    except HarnessError as e:  # graceful degradation: never leave the user with nothing
        fallback = _heuristic_rates(contract)
        fallback.summary = f"AI agent unavailable ({e}). " + fallback.summary
        return fallback.model_dump(), "heuristic"
    return out.model_dump(), f"ai:{config.OPENAI_MODEL}+web_search"


async def review_portfolio(contracts: list[dict], business_type: str, user_id: int) -> tuple[dict, str]:
    if not config.ai_enabled():
        return _heuristic_portfolio(contracts).model_dump(), "heuristic"
    flags = 0
    lines = []
    for c in contracts:
        block, f = fence(f"scope_{c['id']}", c.get("scope") or "", 600)
        flags += f
        lines.append(_contract_brief(c) + "\nscope: " + block)
    prompt = f"Business type: {business_type}\nContracts:\n\n" + "\n\n".join(lines)
    try:
        out = await run_agent(portfolio_agent(), prompt, name="portfolio_agent", user_id=user_id, injection_flags=flags)
    except HarnessError as e:
        fallback = _heuristic_portfolio(contracts)
        fallback.headline = f"AI agent unavailable ({e}). " + fallback.headline
        return fallback.model_dump(), "heuristic"
    valid = {c["id"] for c in contracts}
    for f in out.findings:  # harness-style output check: drop hallucinated ids
        f.contract_ids = [i for i in f.contract_ids if i in valid]
    out.findings = [f for f in out.findings if f.contract_ids]
    return out.model_dump(), f"ai:{config.OPENAI_MODEL}"


async def extract_contract(text: str, file_name: str, user_id: int) -> tuple[ContractExtraction, str]:
    if not config.ai_enabled() or not text.strip():
        return _heuristic_extract(text, file_name), "heuristic"
    block, flags = fence(file_name, text, 15000)
    try:
        out = await run_agent(
            extraction_agent(), f"Document '{file_name}':\n{block}", name="extraction_agent",
            user_id=user_id, trigger="upload", injection_flags=flags, timeout=90, retries=1,
        )
    except HarnessError:
        return _heuristic_extract(text, file_name), "heuristic"
    return out, f"ai:{config.OPENAI_MODEL}"


# ---------------------------------------------------------------- heuristic fallbacks

TYPICAL_SAVINGS = {
    "Software / SaaS": 0.15, "Telecom & Internet": 0.18, "Insurance": 0.10, "Utilities": 0.08,
    "Facilities & Lease": 0.05, "Professional Services": 0.10, "Marketing": 0.12,
    "Logistics & Shipping": 0.12, "Payment Processing": 0.15, "Equipment": 0.08,
}


def _heuristic_rates(c: dict) -> RateRecommendation:
    pct = TYPICAL_SAVINGS.get(c["category"], 0.08)
    value = float(c["annual_value"] or 0)
    if c["line_type"] == "revenue":
        return RateRecommendation(
            summary=(f"Revenue contract with {c['counterparty']}. Small businesses typically raise rates "
                     f"3–5% at renewal to keep pace with costs. Live web benchmarking is off (no OpenAI key)."),
            recommendation="raise_price", confidence="low", estimated_annual_impact=round(value * 0.04, 2),
            next_steps=["Review delivery costs for this client", "Propose a 3–5% increase in the renewal notice",
                        "Add OPENAI_API_KEY to .env for live market benchmarking"],
        )
    return RateRecommendation(
        summary=(f"Businesses that re-quote {c['category'].lower()} contracts at renewal typically save about "
                 f"{int(pct * 100)}%. Live web search is off (no OpenAI key), so this is a rule-of-thumb estimate."),
        recommendation="renegotiate", confidence="low",
        market_low=round(value * (1 - pct * 1.5), 2), market_high=round(value, 2),
        estimated_annual_impact=round(value * pct, 2),
        next_steps=["Collect 2–3 competing quotes", f"Ask {c['counterparty']} to match the best quote",
                    "Add OPENAI_API_KEY to .env for live web rate search"],
    )


def _words(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "of", "to", "a", "in", "on", "our", "all", "per", "services", "service"}
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in stop}


def _heuristic_portfolio(contracts: list[dict]) -> PortfolioReview:
    findings: list[Finding] = []
    expenses = [c for c in contracts if c["line_type"] == "expense"]
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for c in expenses:
        by_cat[c["category"]].append(c)
    for cat, group in by_cat.items():
        if len(group) > 1:
            total = sum(c["annual_value"] for c in group)
            findings.append(Finding(
                title=f"{len(group)} separate {cat} contracts",
                finding_type="consolidation", contract_ids=[c["id"] for c in group],
                estimated_annual_savings=round(total * 0.12, 2),
                rationale=(f"{', '.join(c['counterparty'] for c in group)} all cover {cat}. Combined spend of "
                           f"${total:,.0f}/yr gives leverage for a single bundled agreement."),
                recommended_action="Ask each vendor for a consolidated quote covering all needs; keep the best one.",
                priority="high" if total > 10000 else "medium",
            ))
    seen = set()
    for i, a in enumerate(expenses):
        for b in expenses[i + 1:]:
            if a["category"] == b["category"]:
                continue
            overlap = _words(a.get("scope", "")) & _words(b.get("scope", ""))
            if len(overlap) >= 3 and (a["id"], b["id"]) not in seen:
                seen.add((a["id"], b["id"]))
                smaller = min(a, b, key=lambda c: c["annual_value"])
                findings.append(Finding(
                    title=f"Possible overlap: {a['name']} and {b['name']}",
                    finding_type="redundancy", contract_ids=[a["id"], b["id"]],
                    estimated_annual_savings=round(smaller["annual_value"] * 0.5, 2),
                    rationale=f"Both scopes mention: {', '.join(sorted(overlap)[:6])}.",
                    recommended_action="Confirm whether one contract can cover both needs and drop the other.",
                    priority="medium",
                ))
    total = sum(f.estimated_annual_savings for f in findings)
    return PortfolioReview(
        headline=(f"Found {len(findings)} opportunities worth about ${total:,.0f}/yr (rule-based review; "
                  "add OPENAI_API_KEY for a full AI review)."),
        total_estimated_savings=round(total, 2), findings=findings,
    )


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


def _heuristic_extract(text: str, file_name: str) -> ContractExtraction:
    stem = re.sub(r"[_\-]+", " ", file_name.rsplit(".", 1)[0]).strip().title()
    dates = sorted(DATE_RE.findall(text or ""))
    amounts = [float(a.replace(",", "")) for a in MONEY_RE.findall(text or "")]
    low = (text or "").lower()
    return ContractExtraction(
        name=stem or "Uploaded contract",
        line_type="revenue" if ("client service" in low or "client agrees to pay" in low) else None,
        annual_value=max(amounts) if amounts else None,
        start_date=date.fromisoformat(dates[0]) if dates else None,
        end_date=date.fromisoformat(dates[-1]) if len(dates) > 1 else None,
        auto_renew=True if "automatically renew" in low else None,
    )
