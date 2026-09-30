import copy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from studio.server import Studio, atomic_json, make_handler


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = Studio(self.root)
        self.card = {"id": 1, "name": "Ariel", "fullName": "Ariel - Test", "setCode": "1", "flavorText": "Un texte à corriger.",
                     "abilities": [{"name": "TITRE", "effect": "Texte erroné", "fullText": "TITRE Texte erroné"}]}
        atomic_json(self.root / "output/fr/allCards.json", {"cards": [self.card], "sets": {"1": {"name": "Premier Chapitre"}}, "metadata": {}})
        atomic_json(self.app.correction_path("fr"), {"1": {"flavorText": ["ancien", "texte"]}, "2": {"name": ["A", "B"]}})

    def payload(self):
        return {"language": "fr", "id": 1, "field": "flavorText", "before": "à corriger", "after": "corrigé \\1", "revision": self.app.revision("fr")}

    def test_catalog_and_language_validation(self):
        data = self.app.catalog("fr")
        self.assertEqual(data["cards"][0]["name"], "Ariel")
        self.assertTrue(data["cards"][0]["corrected"])
        self.assertEqual(self.app.catalog("en")["cards"], [])
        with self.assertRaises(ValueError):
            self.app.catalog("../fr")

    def test_correction_preserves_rules_and_literal_backslashes(self):
        payload = self.payload()
        original = self.app.correction_path("fr").read_bytes()
        preview = self.app.correction_preview(payload)
        result = self.app.save_correction(payload)
        stored = self.app.corrections("fr")
        self.assertEqual(stored["2"], {"name": ["A", "B"]})
        self.assertEqual(stored["1"]["flavorText"][:2], ["ancien", "texte"])
        actual = re.sub(*stored["1"]["flavorText"][-2:], self.card["flavorText"], flags=re.DOTALL)
        self.assertEqual(actual, preview["after"])
        self.assertNotEqual(result["revision"], payload["revision"])
        backups = list((self.root / ".fred-studio/backups").glob("*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(self.app.card("fr", 1)["flavorText"], self.card["flavorText"])

    def test_concurrent_and_duplicate_corrections_rejected(self):
        payload = self.payload()
        self.app.save_correction(payload)
        with self.assertRaisesRegex(ValueError, "ont changé"):
            self.app.save_correction(payload)
        payload["revision"] = self.app.revision("fr")
        with self.assertRaisesRegex(ValueError, "déjà"):
            self.app.save_correction(payload)

    def test_preview_nested_abilities_and_no_mutation(self):
        payload = {**self.payload(), "field": "abilities", "before": "erroné", "after": "corrigé"}
        preview = self.app.correction_preview(payload)
        self.assertEqual(preview["matches"], 2)
        self.assertIn("corrigé", preview["after"][0]["effect"])
        self.assertIn("erroné", self.app.card("fr", 1)["abilities"][0]["effect"])

    def test_bad_input_does_not_write(self):
        original = self.app.correction_path("fr").read_bytes()
        for replacement in [{"language": "../en"}, {"id": 999}, {"field": "__proto__"}, {"before": ""}, {"before": "not present"}]:
            with self.assertRaises((ValueError, TypeError)):
                self.app.save_correction({**self.payload(), **replacement})
        self.assertEqual(self.app.correction_path("fr").read_bytes(), original)

    def test_job_command_is_allowlisted_and_single_execution(self):
        for payload in [{"action": "shell"}, {"action": "parse", "cardIds": "1; whoami"}, {"action": "parse", "cardIds": 1}, {"action": "parse", "cardIds": "30-10"}, {"action": "parse", "cardIds": "1-900000"}, {"action": "update", "cardIds": "1"}]:
            with self.assertRaises(ValueError):
                self.app.start_job({"language": "fr", **payload})
        with patch.object(self.app, "diagnostics", return_value={"missing": []}), patch("studio.server.threading.Thread") as thread:
            self.app.start_job({"action": "parse", "language": "fr", "cardIds": "1 20-30", "cached": True})
            args = thread.call_args.kwargs["args"][0]
            self.assertIn("--useCachedOcr", args)
            self.assertIn("20-30", args)
            self.assertTrue(thread.return_value.start.called)
            with self.assertRaisesRegex(ValueError, "déjà en cours"):
                self.app.start_job({"action": "check", "language": "fr"})
            with self.assertRaisesRegex(ValueError, "fin du traitement"):
                self.app.save_correction(self.payload())

    def test_http_auth_host_and_file_boundaries(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        def request(path, headers=None, body=None):
            return urlopen(Request(base + path, headers=headers or {}, data=body), timeout=3)
        with self.assertRaises(HTTPError) as error:
            request("/api/catalog")
        self.assertEqual(error.exception.code, 403)
        headers = {"X-Studio-Token": self.app.token}
        with request("/api/catalog", headers) as response:
            self.assertEqual(json.load(response)["cards"][0]["id"], 1)
        for path in ["/config.json", "/../config.json", "/export?name=../../config.json", "/images/fr/../../config.json"]:
            with self.assertRaises(HTTPError):
                request(path, headers)
        with self.assertRaises(HTTPError) as error:
            request("/api/catalog", {**headers, "Host": "evil.example"})
        self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError) as error:
            request("/api/corrections", {**headers, "Origin": "https://evil.example"}, json.dumps(self.payload()).encode())
        self.assertEqual(error.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
