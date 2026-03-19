"""
KI-Kategorisierung via Claude Haiku.
Batch-Processing: bis zu 20 Transaktionen pro API-Call.
Fallback auf regelbasierte Kategorisierung bei API-Fehler.
"""

import json
import logging
import os
import re
from typing import Optional

import anthropic

from backend.models.transaction import CATEGORIES

logger = logging.getLogger(__name__)

# Regelbasierte Fallbacks – werden VOR dem API-Call geprüft
RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"globus|aldi|lidl|rewe|edeka|netto|penny|biomarkt|e\.?center", re.I), "Lebensmittel"),
    (re.compile(r"lieferando|dominos|call\s*a\s*pizza", re.I), "Lieferando"),
    (re.compile(r"coffee\s*fellows|hai\s*asia|thang\s*long|burger\s*king|mcdonald|döner|imbiss|restaurant|café|kaffee", re.I), "Restaurant/Café"),
    (re.compile(r"amazon|amzn", re.I), "Amazon"),
    (re.compile(r"netflix|spotify|disney|crunchyroll|prime.video|apple.*tv|wow\.tv", re.I), "Streaming"),
    (re.compile(r"blizzard|steam|g2a|epic\s*games|ccp\s*games|humble\s*bundle|playstation|xbox", re.I), "Gaming"),
    (re.compile(r"signal\s*iduna|huk.coburg|cosmos\s*vers|allianz|aok|tk\s*versicherung", re.I), "Versicherung"),
    (re.compile(r"kreditabzahlung|santander|kfw|kredit", re.I), "Kredit & Schulden"),
    (re.compile(r"wertpapier|etf|depot|sparplan|msci|spdr", re.I), "Investments"),
    (re.compile(r"autohaus|tankstelle|kfz.steuer|hem\.|aral|shell|esso|parking|parkhaus", re.I), "Transport & Auto"),
    (re.compile(r"apotheke|arzt|zahnarzt|tierarzt|petfood|futterhaus|shop\s*apotheke|docmorris", re.I), "Gesundheit"),
    (re.compile(r"besoldung|lohn|gehalt|landesamt.*finanzen", re.I), "Einnahmen"),
    (re.compile(r"dauerauftrag|gewerkschaft|gdp|mitglied", re.I), "Sonstiges"),
]

SYSTEM_PROMPT = f"""Du bist ein Finanz-Kategorisierungsassistent. 
Ordne Banktransaktionen einer der folgenden Kategorien zu:

{chr(10).join(f"- {c}" for c in CATEGORIES)}

Regeln:
- "Einnahmen" nur für Gehalt, Lohn, Rückerstattungen und eingehende Überweisungen (positive Beträge)
- "Investments" für ETF-Sparpläne, Wertpapierkäufe, Depot-Transaktionen
- "Kredit & Schulden" für Kreditraten, Daueraufträge zur Schuldentilgung
- "Lieferando" für Lieferando, Domino's, Call a Pizza und ähnliche Lieferdienste
- "Sonstiges" wenn keine andere Kategorie passt

Antworte NUR mit einem JSON-Array, ohne Erklärungen oder Markdown:
[{{"id": 0, "category": "Lebensmittel"}}, {{"id": 1, "category": "Streaming"}}]"""


def _apply_rules(merchant: str, description: str) -> Optional[str]:
    text = f"{merchant} {description}"
    for pattern, category in RULES:
        if pattern.search(text):
            return category
    return None


def categorize_batch(
    items: list[dict],  # [{"id": int, "merchant": str, "description": str, "amount": float}]
) -> dict[int, str]:
    """
    Kategorisiert eine Liste von Transaktionen.
    Gibt {id: category} zurück.
    Schritt 1: Regelbasiert. Schritt 2: Rest via Claude API.
    """
    result: dict[int, str] = {}
    needs_ai: list[dict] = []

    for item in items:
        rule_cat = _apply_rules(item.get("merchant", ""), item.get("description", ""))
        if rule_cat:
            result[item["id"]] = rule_cat
        else:
            needs_ai.append(item)

    if not needs_ai:
        return result

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY nicht gesetzt – Fallback auf 'Sonstiges'")
        for item in needs_ai:
            result[item["id"]] = "Sonstiges"
        return result

    client = anthropic.Anthropic(api_key=api_key)

    # Batches von max. 20
    for batch_start in range(0, len(needs_ai), 20):
        batch = needs_ai[batch_start:batch_start + 20]
        user_content = json.dumps([
            {
                "id": i,
                "merchant": item["merchant"],
                "description": item["description"][:120],
                "amount": item["amount"],
            }
            for i, item in enumerate(batch)
        ], ensure_ascii=False)

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()
            # JSON aus Antwort extrahieren
            json_match = re.search(r"\[.*\]", raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                for entry in parsed:
                    batch_item = batch[entry["id"]]
                    cat = entry.get("category", "Sonstiges")
                    if cat not in CATEGORIES:
                        cat = "Sonstiges"
                    result[batch_item["id"]] = cat
        except Exception as e:
            logger.error(f"Claude API Fehler: {e}")
            for item in batch:
                result.setdefault(item["id"], "Sonstiges")

    return result
