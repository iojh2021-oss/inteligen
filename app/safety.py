"""Deterministic safety gate for user prompts and model outputs.
This narrow first-line filter is not a complete safety classifier or certification.
"""
import re

GUARDRAIL_VERSION = "1.0"
_RULES = (
    ("weapon_or_explosive_operation", re.compile(
        r"(?:how\s+to|steps?\s+to|instructions?\s+to|guide\s+to)"
        r".{0,100}(?:build|make|construct|assemble|fabricate|use|fire|shoot)"
        r".{0,70}(?:bomb|explosive|firearm|gun|weapon|rifle|pistol)|"
        r"(?:چطور|چگونه|روش|آموزش|مراحل)"
        r".{0,80}(?:بمب|مواد\s+منفجره|اسلحه|سلاح|تفنگ|کلت)"
        r".{0,60}(?:بساز|ساخت|استفاده|شلیک)|"
        r"(?:چطور|چگونه|روش\s+ساخت|آموزش\s+ساخت|مراحل\s+ساخت)"
        r".{0,80}(?:بساز|ساخت|استفاده|شلیک)"
        r".{0,60}(?:بمب|مواد\s+منفجره|اسلحه|سلاح|تفنگ|کلت)",
        re.IGNORECASE | re.DOTALL)),
    ("self_harm_instructions", re.compile(
        r"(?:how\s+to|steps?\s+to|instructions?\s+for|ways?\s+to|چطور|چگونه|روش|راهی\s+برای)"
        r".{0,90}(?:hurt\s+myself|harm\s+myself|kill\s+myself|suicide|self[- ]harm|به\s+خودم\s+آسیب|خودکشی)",
        re.IGNORECASE | re.DOTALL)),
    ("cyber_abuse", re.compile(
        r"(?:steal|exfiltrate|dump|harvest)\s+(?:passwords?|credentials?|tokens?)|"
        r"(?:deploy|write|create)\s+(?:ransomware|credential\s+stealer)|"
        r"(?:bypass|evade)\s+(?:authentication|account\s+security)", re.IGNORECASE)),
    ("dangerous_drug_synthesis", re.compile(
        r"(?:synthesize|make|cook|manufacture)\s+(?:methamphetamine|meth|fentanyl|illegal\s+drugs?)",
        re.IGNORECASE)),
)
SAFE_REFUSAL = (
    "این درخواست را نمی‌توانم به شکل دستورالعمل عملیاتیِ پرخطر انجام بدهم. "
    "می‌توانم دربارهٔ اصول ایمنی، پیشگیری، پیامدها یا توضیح علمیِ غیرعملیاتی کمک کنم."
)

class SafetyRejected(ValueError):
    def __init__(self, category: str):
        self.category = category
        super().__init__("Request blocked by the Inteligen safety gate.")

def screen_text(text: str) -> dict:
    """Return an explainable decision without retaining the inspected text."""
    candidate = str(text or "")
    for category, pattern in _RULES:
        if pattern.search(candidate):
            return {"allowed": False, "category": category, "guardrail_version": GUARDRAIL_VERSION}
    return {"allowed": True, "category": None, "guardrail_version": GUARDRAIL_VERSION}
