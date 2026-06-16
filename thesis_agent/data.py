"""Fetch a focused 'fact sheet' of evidence for a ticker via yfinance.

Each fact becomes an Evidence item with a stable ID (E1, E2, ...). The agent may
only cite these IDs, so the quality and labelling of this sheet directly bounds
what the model is allowed to claim. We deliberately keep the sheet small and
human-labelled rather than dumping raw JSON — citations should point at
something a reader can verify.
"""

from dataclasses import dataclass

import yfinance as yf


@dataclass
class Evidence:
    id: str
    category: str
    label: str
    value: str
    source: str


# (info_key, label, category, kind) — kind drives formatting.
_FIELDS: list[tuple[str, str, str, str]] = [
    ("currentPrice", "Current price", "Price", "usd"),
    ("targetMeanPrice", "Analyst mean target price", "Price", "usd"),
    ("fiftyTwoWeekHigh", "52-week high", "Price", "usd"),
    ("fiftyTwoWeekLow", "52-week low", "Price", "usd"),
    ("marketCap", "Market cap", "Size", "big"),
    ("trailingPE", "Trailing P/E", "Valuation", "ratio"),
    ("forwardPE", "Forward P/E", "Valuation", "ratio"),
    ("priceToBook", "Price/Book", "Valuation", "ratio"),
    ("pegRatio", "PEG ratio", "Valuation", "ratio"),
    ("revenueGrowth", "Revenue growth (latest qtr YoY)", "Growth", "pct"),
    ("earningsGrowth", "Earnings growth (latest qtr YoY)", "Growth", "pct"),
    ("grossMargins", "Gross margin", "Profitability", "pct"),
    ("operatingMargins", "Operating margin", "Profitability", "pct"),
    ("profitMargins", "Net profit margin", "Profitability", "pct"),
    ("returnOnEquity", "Return on equity", "Profitability", "pct"),
    ("freeCashflow", "Free cash flow (TTM)", "Cash Flow", "big"),
    ("operatingCashflow", "Operating cash flow (TTM)", "Cash Flow", "big"),
    ("totalCash", "Total cash", "Balance Sheet", "big"),
    ("totalDebt", "Total debt", "Balance Sheet", "big"),
    ("debtToEquity", "Debt/Equity", "Balance Sheet", "ratio"),
    ("currentRatio", "Current ratio", "Balance Sheet", "ratio"),
    ("dividendYield", "Dividend yield", "Capital Return", "pctraw"),
    ("beta", "Beta (volatility vs market)", "Sentiment", "ratio"),
    ("52WeekChange", "52-week price change", "Sentiment", "pct"),
    ("recommendationKey", "Analyst consensus", "Sentiment", "text"),
    ("numberOfAnalystOpinions", "# analysts covering", "Sentiment", "int"),
]


def _fmt(value, kind: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        if kind == "usd":
            return f"${float(value):,.2f}"
        if kind == "big":
            v = float(value)
            for unit, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
                if abs(v) >= scale:
                    return f"${v / scale:,.2f}{unit}"
            return f"${v:,.0f}"
        if kind == "pct":
            return f"{float(value) * 100:,.1f}%"
        if kind == "pctraw":
            # Some yfinance fields (e.g. dividendYield) already come in percent
            # units rather than as a fraction — show them as-is.
            return f"{float(value):,.2f}%"
        if kind == "ratio":
            return f"{float(value):,.2f}"
        if kind == "int":
            return f"{int(value)}"
        return str(value)
    except (TypeError, ValueError):
        return None


def _revenue_trend(ticker: yf.Ticker) -> str | None:
    """Compact multi-year revenue line, oldest -> newest, if available."""
    try:
        stmt = ticker.income_stmt
        if stmt is None or stmt.empty or "Total Revenue" not in stmt.index:
            return None
        row = stmt.loc["Total Revenue"].dropna()
        if row.empty:
            return None
        parts = []
        for period, val in sorted(row.items()):
            year = getattr(period, "year", str(period))
            parts.append(f"{year}: ${float(val) / 1e9:,.1f}B")
        return " → ".join(parts)
    except Exception:
        return None


def build_evidence(symbol: str) -> tuple[str, list[Evidence]]:
    """Return (company_name, evidence_items) for a ticker symbol."""
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    company_name = info.get("longName") or info.get("shortName") or symbol.upper()

    evidence: list[Evidence] = []
    counter = 1

    def add(category: str, label: str, value: str, source: str) -> None:
        nonlocal counter
        evidence.append(Evidence(f"E{counter}", category, label, value, source))
        counter += 1

    sector = info.get("sector")
    industry = info.get("industry")
    if sector or industry:
        add("Profile", "Sector / Industry",
            f"{sector or 'n/a'} / {industry or 'n/a'}", "yfinance .info")

    for key, label, category, kind in _FIELDS:
        formatted = _fmt(info.get(key), kind)
        if formatted is not None:
            add(category, label, formatted, "yfinance .info")

    trend = _revenue_trend(ticker)
    if trend:
        add("Growth", "Annual revenue trend", trend, "yfinance income statement")

    summary = info.get("longBusinessSummary")
    if summary:
        add("Profile", "Business summary", summary[:600].strip(), "yfinance .info")

    try:
        for item in (ticker.news or [])[:5]:
            content = item.get("content", item)
            title = content.get("title") if isinstance(content, dict) else None
            title = title or item.get("title")
            if title:
                add("Recent News", "Headline", title.strip(), "yfinance news")
    except Exception:
        pass

    return company_name, evidence


def format_evidence(evidence: list[Evidence]) -> str:
    """Render the evidence list as the text block handed to the model."""
    lines = []
    for e in evidence:
        lines.append(f"[{e.id}] ({e.category}) {e.label}: {e.value}")
    return "\n".join(lines)
