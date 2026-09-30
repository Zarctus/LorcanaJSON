import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.server import Studio, atomic_json
from studio.workshop import diff_parts, normalize


class WorkshopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = Studio(self.root)
        self.card = {"id": 1, "name": "Ariel", "fullName": "Ariel", "flavorText": "“I chante.”", "cost": 3,
                     "fullText": "CHANT Il gagnne 2 ◊.", "abilities": [{"name": "CHANT", "effect": "Il gagnne 2 ◊.", "fullText": "CHANT Il gagnne 2 ◊."}]}
        self.source = {"culture_invariant_id": 1, "name": "ARIEL", "author": "Artist", "rarity": "COMMON", "ink_cost": 3,
                       "rules_text": "\\Chant\\ Il gagne 2 {L}.", "flavor_text": '"Il chante."'}
        self.write_cards()
        self.write_source()
        atomic_json(self.app.correction_path("fr"), {"2": {"name": ["A", "B"]}})

    def write_cards(self):
        atomic_json(self.root / "output/fr/allCards.json", {"cards": [self.card], "sets": {}, "metadata": {}})
        self.app.cache.clear()

    def write_source(self):
        atomic_json(self.root / "downloads/json/carddata.fr.json", {"cards": {"characters": [self.source]}})
        self.app.workshop.source_cache.clear()

    def payload(self, **extra):
        return {"language": "fr", "id": 1, "fingerprint": self.app.workshop.inspect("fr", 1)["fingerprint"], **extra}

    def test_proposals_are_sourced_and_ignore_case_and_typography(self):
        report = self.app.workshop.inspect("fr", 1)
        paths = [p["path"] for p in report["proposals"]]
        self.assertEqual(set(paths), {"flavorText", "abilities.0.effect"})
        flavor = next(p for p in report["proposals"] if p["path"] == "flavorText")
        self.assertEqual(flavor["after"], "“Il chante.”")
        self.assertTrue(flavor["actionable"])
        self.assertTrue(any(part["changed"] for part in flavor["diff"]["before"]))
        self.assertEqual(normalize("peut-\nêtre"), normalize("peut-être"))

    def test_known_reference_override_prevents_wrong_proposal(self):
        path = self.root / "OutputGeneration/data/verifier/verifierOverrides_fr.json"
        atomic_json(path, {"1": {"flavor_text": ["Il chante", "I chante"]}})
        report = self.app.workshop.inspect("fr", 1)
        self.assertNotIn("flavorText", [p["path"] for p in report["proposals"]])

    def test_existing_rules_are_protected_and_missing_source_not_invented(self):
        atomic_json(self.app.correction_path("fr"), {"1": {"flavorText": ["Il", "I"]}})
        report = self.app.workshop.inspect("fr", 1)
        suggestion = next(p for p in report["proposals"] if p["path"] == "flavorText")
        self.assertFalse(suggestion["actionable"])
        with self.assertRaises(ValueError):
            self.app.workshop.prepare_edit(self.payload(proposal=suggestion["key"]))
        (self.root / "downloads/json/carddata.fr.json").unlink()
        report = self.app.workshop.inspect("fr", 1)
        self.assertEqual(report["proposals"], [])
        self.assertFalse(report["sourceAvailable"])

    def test_stale_reference_and_noneditable_paths_rejected(self):
        payload = self.payload(path="flavorText", after="Autre texte")
        self.source["flavor_text"] = "Nouvelle référence"
        self.write_source()
        with self.assertRaisesRegex(ValueError, "a changé"):
            self.app.workshop.prepare_edit(payload)
        with self.assertRaisesRegex(ValueError, "modifiable"):
            self.app.workshop.prepare_edit(self.payload(path="externalLinks.token", after="value"))

    def test_numeric_and_literal_edit_validation(self):
        for invalid in [True, -1, 100, "4", 3.2]:
            with self.assertRaises(ValueError):
                self.app.workshop.prepare_edit(self.payload(path="cost", after=invalid))
        edit = self.app.workshop.prepare_edit(self.payload(path="cost", after=4))
        self.assertEqual(edit["pair"], [3, 4])
        edit = self.app.workshop.prepare_edit(self.payload(path="flavorText", after="Test \\1"))
        self.assertIn("\\\\1", edit["pair"][1])

    def test_apply_history_verification_and_undo_preserve_other_cards(self):
        proposal = next(p for p in self.app.workshop.inspect("fr", 1)["proposals"] if p["path"] == "flavorText")
        with patch.object(self.app, "check_workshop_ready"), patch.object(self.app, "diagnostics", return_value={"missing": []}), patch("studio.server.threading.Thread"):
            result = self.app.apply_workshop(self.payload(proposal=proposal["key"]))
            rules = self.app.corrections("fr")
            self.assertEqual(rules["2"], {"name": ["A", "B"]})
            self.assertIn("flavorText", rules["1"])
            self.assertEqual(self.app.workshop_history("fr", 1)[0]["status"], "running")
            self.card["flavorText"] = proposal["after"]
            self.write_cards()
            self.app.job["lines"] = ["Found 0 differences between input and output"]
            self.app.finish_workshop(self.app.job, 0)
            self.app.job["state"] = "success"
            self.assertEqual(self.app.workshop_history("fr", 1)[0]["status"], "verified")
            self.app.undo_workshop({"language": "fr", "entry": result["entry"]})
            self.assertNotIn("1", self.app.corrections("fr"))
            self.assertEqual(self.app.corrections("fr")["2"], {"name": ["A", "B"]})

    def test_no_success_claim_when_parser_did_not_apply(self):
        with patch.object(self.app, "check_workshop_ready"), patch.object(self.app, "diagnostics", return_value={"missing": []}), patch("studio.server.threading.Thread"):
            self.app.apply_workshop(self.payload(path="flavorText", after="Autre texte"))
            self.app.job["lines"] = ["Found 0 differences between input and output"]
            self.app.finish_workshop(self.app.job, 0)
            self.assertEqual(self.app.workshop_history("fr", 1)[0]["status"], "not_applied")

    def test_undo_conflict_does_not_overwrite_newer_rules(self):
        with patch.object(self.app, "check_workshop_ready"), patch.object(self.app, "diagnostics", return_value={"missing": []}), patch("studio.server.threading.Thread"):
            result = self.app.apply_workshop(self.payload(path="flavorText", after="Autre texte"))
            rules = self.app.corrections("fr")
            rules["1"]["name"] = ["A", "B"]
            atomic_json(self.app.correction_path("fr"), rules)
            with self.assertRaisesRegex(ValueError, "ont changé"):
                self.app.undo_workshop({"language": "fr", "entry": result["entry"]})
            self.assertEqual(self.app.corrections("fr"), rules)

    def test_diff_content_is_data_not_html(self):
        diff = diff_parts('<script>bad</script>', '<script>good</script>')
        self.assertEqual(''.join(p['text'] for p in diff['before']), '<script>bad</script>')
        self.assertEqual(''.join(p['text'] for p in diff['after']), '<script>good</script>')


if __name__ == "__main__":
    unittest.main()
