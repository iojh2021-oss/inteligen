"""Deterministic, explainable quality signals for Inteligen world outputs.

This is a rubric-based coverage check, not a measure of truth, intelligence, or learning.
It deliberately reports observable text signals and missing criteria for human review.
"""
import re

RUBRICS = {
    "knowledge": {
        "concepts": (r"concept|definition|means|refers to|مفهوم|تعریف|یعنی",),
        "fact_vs_assumption": (r"assumption|inference|fact|verified|فرض|واقعیت|استنباط",),
        "uncertainty": (r"uncertain|uncertainty|unknown|confidence|نامطمئن|عدم قطعیت|نامشخص",),
        "evidence_limits": (r"evidence|source|citation|منبع|شواهد|محدودیت",),
    },
    "reasoning": {
        "ordered_steps": (r"step|first|second|therefore|گام|مرحله|ابتدا|بنابراین",),
        "assumptions": (r"assumption|premise|فرض|پیش‌فرض",),
        "countercheck": (r"counterexample|alternative|falsif|برخلاف|مثال نقض|جایگزین",),
        "conclusion": (r"conclusion|result|نتیجه|جمع‌بندی",),
    },
    "science": {
        "hypothesis": (r"hypothesis|hypotheses|فرضیه",),
        "prediction": (r"predict|prediction|expected|پیش‌بینی|انتظار",),
        "test": (r"experiment|test|measure|آزمایش|آزمون|اندازه‌گیری",),
        "limitations": (r"limitation|limit|risk|محدودیت|ریسک",),
    },
    "creativity": {
        "multiple_ideas": (r"idea|option|approach|alternative|ایده|گزینه|راهکار|رویکرد",),
        "tradeoffs": (r"trade.?off|advantage|disadvantage|pros|cons|مزیت|عیب|مبادله",),
        "original_combination": (r"combine|adapt|reframe|ترکیب|بازطراحی|تلفیق",),
        "practicality": (r"practical|feasible|implement|عملی|امکان‌پذیر|اجرا",),
    },
    "learning": {
        "identified_gap": (r"gap|weakness|missing|ضعف|شکاف|کمبود",),
        "measurable_metric": (r"metric|measure|score|rate|عدد|شاخص|امتیاز|نرخ",),
        "evaluation_test": (r"evaluate|evaluation|benchmark|test|ارزیابی|معیار|آزمون",),
        "improvement": (r"improve|improvement|next iteration|بهبود|تکرار بعدی",),
    },
}

def evaluate_text(world: str, output: str) -> dict:
    """Return transparent criterion hits; never interpret this as factual correctness."""
    rubric = RUBRICS.get(world)
    if rubric is None:
        raise ValueError(f"Unknown world: {world}")
    text = str(output or "")
    normalized = text.casefold()
    checks = {
        criterion: any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)
        for criterion, patterns in rubric.items()
    }
    passed = sum(checks.values())
    total = len(checks)
    return {
        "world": world,
        "score": round(100 * passed / total),
        "passed": passed,
        "total": total,
        "checks": checks,
        "missing": [name for name, ok in checks.items() if not ok],
        "output_chars": len(text),
        "output_words": len(re.findall(r"\\w+", text, flags=re.UNICODE)),
        "interpretation": "textual rubric coverage only; not truth, correctness, intelligence, or learning",
    }

def evaluate_worlds(outputs: dict) -> dict:
    results = {}
    for world in RUBRICS:
        value = outputs.get(world, "")
        if str(value).startswith("(unavailable:"):
            results[world] = {"world": world, "status": "unavailable", "score": None,
                              "missing": list(RUBRICS[world]), "output_chars": 0}
        else:
            results[world] = {"status": "evaluated", **evaluate_text(world, str(value))}
    available = [v["score"] for v in results.values() if v["score"] is not None]
    return {
        "rubric_version": 1,
        "scope": "deterministic text-coverage signals; human review still required",
        "overall_score": round(sum(available) / len(available)) if available else None,
        "evaluated_worlds": len(available),
        "worlds": results,
    }
