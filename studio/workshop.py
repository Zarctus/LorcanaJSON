"""Local, explainable correction suggestions; no remote AI or invented card text."""
from __future__ import annotations

import copy
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re

from OutputGeneration.Verifier import _prepareInputCardFlavorText, _prepareInputCardRulesText
from util import Language

LABELS = {"name": "Nom", "version": "Sous-titre", "artistsText": "Illustrateur", "flavorText": "Texte d’ambiance",
          "cost": "Coût", "strength": "Force", "willpower": "Volonté", "lore": "Lore", "moveCost": "Déplacement"}
SCALARS = set(LABELS)
NUMERIC = {"cost", "strength", "willpower", "lore", "moveCost"}
QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "„": '"', "\u00a0": " "})


def normalized_map(value):
    """Normalize only typography, keeping offsets into the unmodified text."""
    text, starts, ends = [], [], []
    for match in re.finditer(r"\.\.\.|\s+|.", str(value), re.DOTALL):
        raw = match.group()
        if "\n" in raw and text and text[-1] in {"-", "—"}:
            continue
        char = " " if raw.isspace() else "…" if raw == "..." else raw.translate(QUOTES)
        text.append(char)
        starts.append(match.start())
        ends.append(match.end())
    return "".join(text), starts, ends


def normalize(value):
    return normalized_map(value)[0].strip() if isinstance(value, str) else value


def diff_parts(before, after):
    left = re.findall(r"\s+|[\w]+|[^\w\s]", str(before), re.UNICODE)
    right = re.findall(r"\s+|[\w]+|[^\w\s]", str(after), re.UNICODE)
    result = {"before": [], "after": []}
    for tag, a, b, c, d in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if a != b:
            result["before"].append({"text": "".join(left[a:b]), "changed": tag != "equal"})
        if c != d:
            result["after"].append({"text": "".join(right[c:d]), "changed": tag != "equal"})
    return result


def value_at(card, path):
    value = card
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def editable_fields(card):
    result = []
    for field, label in LABELS.items():
        if field in card and (type(card[field]) is int or isinstance(card[field], str)):
            result.append({"path": field, "field": field, "label": label, "value": card[field], "numeric": field in NUMERIC})
    for i, ability in enumerate(card.get("abilities", [])):
        for key, label in [("name", "Titre"), ("effect", "Texte")]:
            if isinstance(ability.get(key), str) and ability[key]:
                result.append({"path": f"abilities.{i}.{key}", "field": "abilities", "label": f"Capacité {i + 1} · {label}", "value": ability[key], "numeric": False})
        if "effect" not in ability and isinstance(ability.get("fullText"), str):
            result.append({"path": f"abilities.{i}.fullText", "field": "abilities", "label": f"Capacité {i + 1}", "value": ability["fullText"], "numeric": False})
    for i, effect in enumerate(card.get("effects", [])):
        if isinstance(effect, str):
            result.append({"path": f"effects.{i}", "field": "effects", "label": f"Effet {i + 1}", "value": effect, "numeric": False})
    return result


def revision(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def preserve_typography(current, reference):
    """Transfer changed spans from the reference without rewriting equal typography."""
    old, starts, ends = normalized_map(current)
    new = normalized_map(reference)[0]
    result = current
    for tag, a, b, c, d in reversed(SequenceMatcher(None, old, new, autojunk=False).get_opcodes()):
        if tag == "equal":
            continue
        start = starts[a] if a < len(starts) else len(current)
        end = ends[b - 1] if b > a else start
        result = result[:start] + new[c:d] + result[end:]
    return result


class Workshop:
    def __init__(self, app):
        self.app = app
        self.source_cache = {}
        self.review_cache = {}
        self.rules_cache = {}

    def rules(self, path):
        stamp = path.stat().st_mtime_ns if path.exists() else 0
        if path not in self.rules_cache or self.rules_cache[path][0] != stamp:
            self.rules_cache[path] = (stamp, json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {})
        return self.rules_cache[path][1]

    def sources(self, lang):
        root = self.app.root
        path = root / "downloads/json" / f"carddata.{lang}.json"
        overrides = root / "OutputGeneration/data/verifier" / f"verifierOverrides_{lang}.json"
        stamp = (path.stat().st_mtime_ns if path.exists() else 0, overrides.stat().st_mtime_ns if overrides.exists() else 0)
        if lang not in self.source_cache or self.source_cache[lang][0] != stamp:
            data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
            by_id = {c["culture_invariant_id"]: c for cards in data.get("cards", {}).values() for c in cards}
            rules = json.loads(overrides.read_text(encoding="utf-8-sig")) if overrides.exists() else {}
            self.source_cache[lang] = (stamp, by_id, rules)
        return self.source_cache[lang]

    def prepared_source(self, lang, card_id):
        _, cards, overrides = self.sources(lang)
        if card_id not in cards:
            return None
        card = copy.deepcopy(cards[card_id])
        language = Language.getLanguageByCode(lang)
        _prepareInputCardRulesText(card, language)
        _prepareInputCardFlavorText(card, language)
        if card.get("author") == "Juan Pablo Velázquez":
            card["author"] = "Juan Pablo Velázquez López"
        for field, pairs in overrides.get(str(card_id), {}).items():
            if field.startswith("_"):
                continue
            for i in range(0, len(pairs), 2):
                before, after = pairs[i:i + 2]
                if before is None:
                    if after is None:
                        card.pop(field, None)
                    elif field not in card:
                        card[field] = after
                elif isinstance(card.get(field), str):
                    card[field] = re.sub(before, after, card[field], flags=re.DOTALL)
                elif card.get(field) == before:
                    card[field] = after
        return card

    def inspect(self, lang, card_id):
        card = self.app.card(lang, card_id)
        fields = editable_fields(card)
        source = self.prepared_source(lang, card["id"])
        corrections = self.rules(self.app.correction_path(lang)).get(str(card["id"]), {})
        general_path = self.app.root / "OutputGeneration/data/outputDataCorrections/outputDataCorrections.json"
        general = self.rules(general_path)
        protected = set(corrections) | set(general.get(str(card["id"]), {}))
        proposals = []
        notes = []

        def add(entry, after, reason, confidence="reference", whole=True):
            before = entry["value"]
            if before == after or normalize(before) == normalize(after):
                return
            proposal = {"path": entry["path"], "field": entry["field"], "label": entry["label"], "before": before, "after": after,
                        "reason": reason, "confidence": confidence, "source": "Règle typographique locale" if confidence == "mechanical" else "Référence officielle locale, exceptions du projet appliquées",
                        "actionable": entry["field"] not in protected or confidence == "mechanical", "whole": whole}
            if not proposal["actionable"]:
                proposal["reason"] += " Une correction existe déjà sur ce champ : comparez avec l’image."
                proposal["confidence"] = "review"
            proposal["diff"] = diff_parts(before, after)
            proposal["key"] = revision(proposal)[:20]
            if not any(p["path"] == proposal["path"] and p["after"] == proposal["after"] for p in proposals):
                proposals.append(proposal)

        # Official scalar values. Missing reference values and ERRATA never become deletions.
        if source:
            mapping = {"name": "name", "version": "subtitle", "artistsText": "author", "flavorText": "flavor_text",
                       "cost": "ink_cost", "strength": "strength", "willpower": "willpower", "lore": "quest_value", "moveCost": "move_cost"}
            for entry in fields:
                key = mapping.get(entry["path"])
                ref = source.get(key) if key else None
                current = entry["value"]
                if ref is None or ref == "" or ref == "ERRATA" or normalize(current) == normalize(ref):
                    continue
                if key in {"name", "subtitle"} and isinstance(ref, str) and normalize(current).casefold() == normalize(ref).casefold():
                    continue
                if type(current) is int and type(ref) is int:
                    add(entry, ref, "Cette valeur diffère de la référence.")
                elif isinstance(current, str) and isinstance(ref, str) and current:
                    ratio = SequenceMatcher(None, normalize(current), normalize(ref), autojunk=False).ratio()
                    after = preserve_typography(current, ref)
                    add(entry, after, "Le texte diffère de la référence.", "reference" if ratio >= .72 else "review")
                    if ratio < .72 and proposals and proposals[-1]["path"] == entry["path"]:
                        proposals[-1]["actionable"] = False
            # Align short stretches of rules text with a single editable ability/effect.
            before = normalize(card.get("fullText", ""))
            after = normalize(source.get("rules_text", ""))
            if before and after and before != after:
                a, b = before.split(), after.split()
                matcher = SequenceMatcher(None, a, b, autojunk=False)
                matched = 0
                groups = list(matcher.get_grouped_opcodes(2))
                if matcher.ratio() >= .65:
                    for group in groups:
                        for context in (2, 1, 0):
                            first, last = group[0], group[-1]
                            a_start = max(first[1], first[2] - context) if first[0] == "equal" else first[1]
                            b_start = max(first[3], first[4] - context) if first[0] == "equal" else first[3]
                            a_end = min(last[2], last[1] + context) if last[0] == "equal" else last[2]
                            b_end = min(last[4], last[3] + context) if last[0] == "equal" else last[4]
                            old, new = " ".join(a[a_start:a_end]), " ".join(b[b_start:b_end])
                            candidates = [f for f in fields if f["field"] in {"abilities", "effects"} and old and normalize(f["value"]).count(old) == 1]
                            if len(candidates) == 1:
                                break
                        if len(candidates) != 1:
                            continue
                        entry = candidates[0]
                        text, starts, ends = normalized_map(entry["value"])
                        start = text.index(old)
                        raw_old = entry["value"][starts[start]:ends[start + len(old) - 1]]
                        raw_new = preserve_typography(raw_old, new)
                        add({**entry, "value": raw_old}, raw_new, "Écart localisé dans le texte de la capacité.", whole=False)
                        matched += 1
                if matched < len(groups):
                    notes.append({"label": "Texte des capacités à relire", "reason": "La structure diffère de la référence. Une correction automatique pourrait changer le sens.", "diff": diff_parts(card.get("fullText", ""), source.get("rules_text", ""))})
        else:
            notes.append({"label": "Référence indisponible", "reason": "Téléchargez les données officielles de cette langue pour obtenir des propositions. L’édition manuelle reste disponible."})

        fingerprint = revision({"card": card, "source": source, "corrections": corrections, "general": general.get(str(card["id"]), {})})
        return {"proposals": proposals, "notes": notes, "fields": fields, "fingerprint": fingerprint, "sourceAvailable": source is not None}

    def review(self, lang):
        source_stamp = self.sources(lang)[0]
        output = self.app.root / "output" / lang / "allCards.json"
        general = self.app.root / "OutputGeneration/data/outputDataCorrections/outputDataCorrections.json"
        stamp = (source_stamp, output.stat().st_mtime_ns if output.exists() else 0, self.app.revision(lang), general.stat().st_mtime_ns if general.exists() else 0)
        if lang in self.review_cache and self.review_cache[lang][0] == stamp:
            return self.review_cache[lang][1]
        result = []
        for card in self.app.data(lang)["cards"]:
            report = self.inspect(lang, card["id"])
            if report["proposals"] or (report["sourceAvailable"] and report["notes"]):
                result.append({"id": card["id"], "proposals": len(report["proposals"]), "actionable": sum(p["actionable"] for p in report["proposals"]), "notes": len(report["notes"])})
        self.review_cache[lang] = (stamp, result)
        return result

    def prepare_edit(self, payload):
        lang = self.app.language(payload.get("language"))
        card = self.app.card(lang, payload.get("id"))
        report = self.inspect(lang, card["id"])
        if payload.get("fingerprint") != report["fingerprint"]:
            raise ValueError("La carte ou la référence a changé. Actualisez la fiche avant d’appliquer.")
        if payload.get("proposal"):
            proposal = next((p for p in report["proposals"] if p["key"] == payload["proposal"]), None)
            if not proposal or not proposal["actionable"]:
                raise ValueError("Cette proposition doit être relue ou n’est plus disponible.")
            edit = copy.deepcopy(proposal)
        else:
            field = next((f for f in report["fields"] if f["path"] == payload.get("path")), None)
            if field is None:
                raise ValueError("Ce champ n’est pas modifiable.")
            after = payload.get("after")
            if field["numeric"]:
                if type(after) is not int or not 0 <= after <= 99:
                    raise ValueError("Saisissez un nombre entier entre 0 et 99.")
            elif not isinstance(after, str) or not after.strip() or len(after) > 20000:
                raise ValueError("Le texte corrigé doit contenir entre 1 et 20 000 caractères.")
            edit = {**field, "before": field["value"], "after": after, "whole": True, "source": "Modification manuelle"}
        if edit["before"] == edit["after"]:
            raise ValueError("Aucune modification à appliquer.")
        current = value_at(card, edit["path"])
        if type(edit["before"]) is int:
            pattern, replacement = edit["before"], edit["after"]
            expected = edit["after"]
        else:
            if not edit["before"]:
                raise ValueError("L’ajout de texte dans un champ vide n’est pas pris en charge ici.")
            pattern = r"\s+".join(re.escape(part) for part in re.split(r"\s+", edit["before"]))
            if edit["whole"]:
                pattern = r"\A" + pattern + r"\Z"
            replacement = edit["after"].replace("\\", "\\\\")
            expected = current.replace(edit["before"], edit["after"])
        return {**edit, "pair": [pattern, replacement], "expected": expected, "original": current, "diff": diff_parts(current, expected)}
