from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import webbrowser
from urllib.request import Request, urlopen
from studio.workshop import Workshop, normalize, value_at

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).parent / "web"
LANGUAGES = {"fr": "Français", "en": "English", "de": "Deutsch", "it": "Italiano"}
ACTIONS = {"check", "download", "update", "parse", "verify", "updateExternalLinks"}
FIELDS = {"abilities", "effects", "flavorText", "name", "version", "artistsText"}


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".studio-tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Studio:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.cache = {}
        self.lock = threading.RLock()
        self.job = None
        self.process = None
        self.token = secrets.token_urlsafe(32)
        self.last_seen = time.time()
        self.workshop = Workshop(self)

    def language(self, value):
        if value not in LANGUAGES:
            raise ValueError("Langue non prise en charge.")
        return value

    def data(self, lang):
        path = self.root / "output" / self.language(lang) / "allCards.json"
        if not path.exists():
            return {"cards": [], "sets": {}, "metadata": {}}
        stamp = path.stat().st_mtime_ns
        with self.lock:
            if lang not in self.cache or self.cache[lang][0] != stamp:
                data = read_json(path)
                self.cache[lang] = (stamp, data)
            return self.cache[lang][1]

    def correction_path(self, lang):
        return self.root / "OutputGeneration/data/outputDataCorrections" / f"outputDataCorrections_{self.language(lang)}.json"

    def corrections(self, lang):
        return read_json(self.correction_path(lang), {})

    def card(self, lang, card_id):
        card = next((c for c in self.data(lang)["cards"] if c["id"] == int(card_id)), None)
        if card is None:
            raise ValueError("Cette carte n’existe pas dans la base locale.")
        return card

    def revision(self, lang):
        path = self.correction_path(lang)
        return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()

    def catalog(self, lang):
        data = self.data(lang)
        corrections = self.corrections(lang)
        keys = ("id", "name", "version", "fullName", "setCode", "number", "rarity", "color", "type", "cost", "story", "inkwell")
        return {
            "cards": [{**{k: c.get(k) for k in keys}, "corrected": str(c["id"]) in corrections} for c in data["cards"]],
            "sets": data.get("sets", {}), "metadata": data.get("metadata", {}),
            "languages": [{"code": key, "label": value, "available": (self.root / "output" / key / "allCards.json").exists()} for key, value in LANGUAGES.items()],
        }

    def detail(self, lang, card_id):
        return {"card": self.card(lang, card_id), "corrections": self.corrections(lang).get(str(card_id), {}), "revision": self.revision(lang),
                "workshop": self.workshop.inspect(lang, card_id), "history": self.workshop_history(lang, card_id)}

    def history_file(self):
        return self.root / ".fred-studio/workshop-history.json"

    def workshop_history(self, lang, card_id):
        public = {"key", "path", "label", "before", "after", "created", "status", "message", "jobId", "undoOf"}
        history = read_json(self.history_file(), [])
        return [{k: v for k, v in row.items() if k in public} for row in reversed(history)
                if row["language"] == lang and row["cardId"] == int(card_id)][:15]

    def check_workshop_ready(self, lang, card_id):
        if self.job and self.job["state"] == "running":
            raise ValueError("Un traitement est en cours. Attendez sa fin pour appliquer une correction.")
        missing = self.diagnostics()["missing"]
        if missing:
            raise ValueError("Installez les dépendances du moteur avant d’appliquer : " + ", ".join(missing))
        for relative in [f"downloads/json/carddata.{lang}.json", f"downloads/images/{lang}/{card_id}.jpg", "output/externalLinks.json"]:
            if not (self.root / relative).is_file():
                raise ValueError(f"Le moteur a besoin du fichier {relative}. Téléchargez les données manquantes.")

    def apply_workshop(self, payload):
        with self.lock:
            lang = self.language(payload.get("language"))
            card_id = int(payload.get("id"))
            self.check_workshop_ready(lang, card_id)
            edit = self.workshop.prepare_edit(payload)
            data = self.corrections(lang)
            old_rules = copy.deepcopy(data.get(str(card_id)))
            entries = data.setdefault(str(card_id), {})
            rules = entries.setdefault(edit["field"], [])
            if not isinstance(rules, list) or len(rules) % 2:
                raise ValueError("Format de correction existant incompatible.")
            if any(rules[i:i + 2] == edit["pair"] for i in range(0, len(rules), 2)):
                raise ValueError("Cette règle est déjà enregistrée. Utilisez Réessayer dans l’historique.")
            rules.extend(edit["pair"])
            entry = {"key": secrets.token_hex(8), "language": lang, "cardId": card_id, "path": edit["path"], "label": edit["label"],
                     "before": edit["original"], "after": edit["expected"], "source": edit["source"], "created": time.time(), "status": "queued",
                     "rulesBefore": old_rules, "rulesAfter": copy.deepcopy(entries)}
            return self.commit_workshop(lang, data, entry)

    def commit_workshop(self, lang, corrections, entry):
        path = self.correction_path(lang)
        backup = self.root / ".fred-studio/backups" / f"{path.stem}-{time.time_ns()}.json"
        original = path.read_bytes() if path.exists() else None
        if original is not None:
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(original)
        history = read_json(self.history_file(), [])
        history.append(entry)
        atomic_json(path, corrections)
        try:
            atomic_json(self.history_file(), history)
        except Exception:
            if original is not None:
                path.write_bytes(original)
            else:
                path.unlink(missing_ok=True)
            raise
        # The lock is held through launch; the worker cannot finish before its history link exists.
        job = self.start_job({"language": lang, "action": "parse", "cardIds": str(entry["cardId"]), "cached": True})
        self.job["workshop"] = entry["key"]
        self.job["stage"] = "parse"
        entry["jobId"] = job["id"]
        entry["status"] = "running"
        atomic_json(self.history_file(), history)
        return {"job": copy.deepcopy(self.job), "entry": entry["key"]}

    def undo_workshop(self, payload):
        with self.lock:
            lang = self.language(payload.get("language"))
            history = read_json(self.history_file(), [])
            previous = next((h for h in history if h["key"] == payload.get("entry") and h["language"] == lang), None)
            if previous is None or previous.get("undoOf") or previous["status"] == "undone":
                raise ValueError("Cette correction n’est plus annulable.")
            self.check_workshop_ready(lang, previous["cardId"])
            data = self.corrections(lang)
            current = data.get(str(previous["cardId"]))
            if current != previous["rulesAfter"]:
                raise ValueError("Les règles de cette carte ont changé. Annulez d’abord sa correction la plus récente.")
            before = value_at(self.card(lang, previous["cardId"]), previous["path"])
            if previous["rulesBefore"] is None:
                data.pop(str(previous["cardId"]), None)
            else:
                data[str(previous["cardId"])] = copy.deepcopy(previous["rulesBefore"])
            entry = {"key": secrets.token_hex(8), "language": lang, "cardId": previous["cardId"], "path": previous["path"],
                     "label": previous["label"], "before": before, "after": previous["before"], "created": time.time(), "status": "queued",
                     "undoOf": previous["key"], "rulesBefore": current, "rulesAfter": previous["rulesBefore"]}
            return self.commit_workshop(lang, data, entry)

    def retry_workshop(self, payload):
        with self.lock:
            lang = self.language(payload.get("language"))
            history = read_json(self.history_file(), [])
            entry = next((h for h in history if h["key"] == payload.get("entry") and h["language"] == lang), None)
            if entry is None or entry["status"] not in {"failed", "not_applied", "interrupted"}:
                raise ValueError("Cette correction ne nécessite pas de relance.")
            self.check_workshop_ready(lang, entry["cardId"])
            if self.corrections(lang).get(str(entry["cardId"])) != entry["rulesAfter"]:
                raise ValueError("Les règles ont changé depuis cette correction. Rouvrez la carte.")
            job = self.start_job({"language": lang, "action": "parse", "cardIds": str(entry["cardId"]), "cached": True})
            self.job.update(workshop=entry["key"], stage="parse")
            entry.update(status="running", jobId=job["id"])
            atomic_json(self.history_file(), history)
            return {"job": copy.deepcopy(self.job), "entry": entry["key"]}

    def finish_workshop(self, job, code):
        history = read_json(self.history_file(), [])
        entry = next(h for h in history if h["key"] == job["workshop"])
        message = "Le traitement a échoué. La règle est conservée ; consultez le journal avant de réessayer."
        status = "failed"
        if code == 0:
            actual = value_at(self.card(entry["language"], entry["cardId"]), entry["path"])
            if normalize(actual) == normalize(entry["after"]):
                counts = re.findall(r"Found (\d+) differences between input and output", "\n".join(job["lines"]))
                clean = bool(counts) and counts[-1] == "0"
                status = "verified" if clean else "applied"
                message = "Correction appliquée ; aucune différence signalée par le vérificateur." if clean else "Correction appliquée. D’autres différences restent à relire dans le journal."
            else:
                status = "not_applied"
                message = "La carte régénérée ne correspond pas au résultat attendu. La règle est enregistrée, mais cette correction reste à relire."
        entry.update(status=status, message=message)
        if entry.get("undoOf") and status in {"applied", "verified"}:
            original = next(h for h in history if h["key"] == entry["undoOf"])
            original["status"] = "undone"
        atomic_json(self.history_file(), history)
        job["workshopResult"] = {"status": status, "message": message, "cardId": entry["cardId"], "language": entry["language"]}

    def correction_preview(self, payload):
        lang = self.language(payload.get("language"))
        card = self.card(lang, payload.get("id"))
        field = payload.get("field")
        old, new = payload.get("before"), payload.get("after")
        if field not in FIELDS or not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("Champ de correction invalide.")
        if not old or old == new or max(len(old), len(new)) > 20000:
            raise ValueError("Saisissez le texte à remplacer et une correction différente.")
        before = card.get(field)
        count = 0

        def replace(value):
            nonlocal count
            if isinstance(value, str):
                count += value.count(old)
                return value.replace(old, new)
            if isinstance(value, list):
                return [replace(v) for v in value]
            if isinstance(value, dict):
                return {k: replace(v) for k, v in value.items()}
            return value

        after = replace(before)
        if not count:
            raise ValueError("Ce texte n’a pas été trouvé dans le champ sélectionné.")
        return {"before": before, "after": after, "matches": count, "pattern": re.escape(old), "replacement": new.replace("\\", "\\\\")}

    def save_correction(self, payload):
        with self.lock:
            if self.job and self.job["state"] == "running":
                raise ValueError("Attendez la fin du traitement avant de modifier les corrections.")
            preview = self.correction_preview(payload)
            lang = payload["language"]
            if payload.get("revision") != self.revision(lang):
                raise ValueError("Les corrections ont changé. Rouvrez la carte avant d’enregistrer.")
            path = self.correction_path(lang)
            data = self.corrections(lang)
            entries = data.setdefault(str(payload["id"]), {})
            rules = entries.setdefault(payload["field"], [])
            if not isinstance(rules, list) or len(rules) % 2:
                raise ValueError("Format de correction existant incompatible.")
            pair = [preview["pattern"], preview["replacement"]]
            if any(rules[i:i + 2] == pair for i in range(0, len(rules), 2)):
                raise ValueError("Cette correction est déjà enregistrée.")
            backup = self.root / ".fred-studio/backups" / f"{path.stem}-{time.time_ns()}.json"
            if path.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
            rules.extend(pair)
            atomic_json(path, data)
            return {"ok": True, "revision": self.revision(lang), "corrections": entries}

    def diagnostics(self):
        modules = {"requests": "requests", "cv2": "opencv-python", "PIL": "Pillow", "tesserocr": "tesserocr", "natsort": "natsort", "pymysql": "pymysql", "mysql": "mysql-connector-python"}
        missing = [package for module, package in modules.items() if importlib.util.find_spec(module) is None]
        return {"python": sys.executable, "root": str(self.root), "missing": missing, "ready": not missing,
                "models": {lang: (self.root / filename).exists() for lang, filename in [("fr", "fra.traineddata"), ("en", "eng.traineddata")]}}

    def start_job(self, payload):
        action = payload.get("action")
        lang = self.language(payload.get("language"))
        if action not in ACTIONS:
            raise ValueError("Action non prise en charge.")
        card_ids = payload.get("cardIds", "")
        if not isinstance(card_ids, str):
            raise ValueError("La sélection doit être une liste d’identifiants.")
        card_ids = card_ids.strip()
        if card_ids and not re.fullmatch(r"\d+(?:-\d+)?(?:\s+\d+(?:-\d+)?)*", card_ids):
            raise ValueError("Identifiants invalides. Exemple : 1 12 20-30.")
        if len(card_ids) > 5000:
            raise ValueError("La sélection est trop longue.")
        if card_ids and action not in {"parse", "verify"}:
            raise ValueError("La sélection de cartes est disponible pour Analyser et Vérifier.")
        for value in card_ids.split():
            bounds = [int(x) for x in value.split("-")]
            if min(bounds) < 1 or max(bounds) > 1000000 or (len(bounds) == 2 and (bounds[0] > bounds[1] or bounds[1] - bounds[0] > 20000)):
                raise ValueError("La plage d’identifiants est invalide ou trop grande.")
        missing = self.diagnostics()["missing"]
        if missing:
            raise ValueError("Le moteur Python nécessite : " + ", ".join(missing) + ". Consultez les paramètres.")
        args = [sys.executable, "-u", "-m", "main", action, "--language", lang, "--loglevel", "info"]
        if card_ids:
            args += ["--cardIds", *card_ids.split()]
        if payload.get("cached") and action in {"parse", "update"}:
            args.append("--useCachedOcr")
        with self.lock:
            if self.job and self.job["state"] == "running":
                raise ValueError("Un traitement est déjà en cours.")
            self.job = {"id": secrets.token_hex(6), "action": action, "language": lang, "state": "running", "started": time.time(), "lines": [], "exitCode": None}
            threading.Thread(target=self.run_job, args=(args, self.job), daemon=True).start()
            return copy.deepcopy(self.job)

    def run_job(self, args, job):
        log_dir = self.root / ".fred-studio/runs"
        code = -1
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            with (log_dir / (job["id"] + ".log")).open("w", encoding="utf-8") as logfile:
                commands = [args]
                with self.lock:
                    if job.get("workshop"):
                        commands.append([*args[:4], "verify", *args[5:]])
                        commands[-1] = [arg for arg in commands[-1] if arg != "--useCachedOcr"]
                for step, command in enumerate(commands):
                    with self.lock:
                        job["stage"] = "verify" if step else job["action"]
                    process = subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                               text=True, encoding="utf-8", errors="replace", env=env,
                                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    with self.lock:
                        self.process = process
                    for line in process.stdout:
                        logfile.write(line)
                        logfile.flush()
                        with self.lock:
                            job["lines"].append(line.rstrip())
                            job["lines"] = job["lines"][-1500:]
                    code = process.wait()
                    if code:
                        break
        except Exception as exc:
            with self.lock:
                job["lines"].append(str(exc))
        finally:
            with self.lock:
                if job.get("workshop"):
                    try:
                        self.finish_workshop(job, code)
                    except Exception as exc:
                        job["lines"].append(f"Vérification de la correction impossible : {exc}")
                        job["workshopResult"] = {"status": "failed", "message": "Impossible de confirmer la correction. Consultez le journal."}
                        code = -1
                job.update(state="success" if code == 0 else "error", exitCode=code, finished=time.time())
                self.process = None
                atomic_json(self.root / ".fred-studio/last-run.json", job)

    def status(self):
        with self.lock:
            result = copy.deepcopy(self.job) if self.job else read_json(self.root / ".fred-studio/last-run.json")
            if result and not self.job and result["state"] == "running":
                result["state"] = "interrupted"
            return result

    def exports(self, lang):
        folder = self.root / "output" / self.language(lang)
        return [{"name": p.name, "size": p.stat().st_size, "modified": p.stat().st_mtime} for p in sorted(folder.glob("*")) if p.is_file() and p.suffix in {".json", ".zip", ".xml"}]


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, data, content_type="application/json; charset=utf-8", status=200, extra=None):
            if isinstance(data, (dict, list)) or data is None:
                data = json.dumps(data, ensure_ascii=False).encode("utf-8")
            elif isinstance(data, str):
                data = data.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "private, max-age=60" if content_type.startswith("image/") else "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.send({"error": "Hôte refusé."}, status=403)
            parsed = urlsplit(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            lang = query.get("language", ["fr"])[0]
            try:
                if path.startswith("/api/"):
                    if not secrets.compare_digest(self.headers.get("X-Studio-Token", ""), app.token):
                        return self.send({"error": "Session expirée. Rouvrez FRED Studio."}, status=403)
                    app.last_seen = time.time()
                    routes = {
                        "/api/catalog": lambda: app.catalog(lang),
                        "/api/card": lambda: app.detail(lang, int(query.get("id", ["0"])[0])),
                        "/api/job": app.status,
                        "/api/diagnostics": app.diagnostics,
                        "/api/exports": lambda: app.exports(lang),
                        "/api/workshop/review": lambda: app.workshop.review(lang),
                    }
                    if path not in routes:
                        return self.send({"error": "Introuvable"}, status=404)
                    return self.send(routes[path]())
                if path.startswith("/images/"):
                    match = re.fullmatch(r"/images/(fr|en|de|it)/(\d+)\.jpg", path)
                    if not match:
                        raise ValueError("Image invalide")
                    image = app.root / "downloads/images" / match[1] / (match[2] + ".jpg")
                    if image.exists():
                        return self.send(image.read_bytes(), "image/jpeg")
                    return self.send((STATIC / "placeholder.svg").read_bytes(), "image/svg+xml")
                if path == "/export":
                    if not secrets.compare_digest(query.get("token", [""])[0], app.token):
                        return self.send({"error": "Session invalide"}, status=403)
                    name = query.get("name", [""])[0]
                    if name not in {p["name"] for p in app.exports(lang)}:
                        raise ValueError("Export invalide")
                    file = app.root / "output" / lang / name
                    return self.send(file.read_bytes(), "application/octet-stream", extra={"Content-Disposition": f'attachment; filename="{name}"'})
                static_files = {"/": "index.html", "/app.js": "app.js", "/workshop.js": "workshop.js", "/style.css": "style.css", "/workshop.css": "workshop.css", "/favicon.svg": "favicon.svg", "/placeholder.svg": "placeholder.svg"}
                if path not in static_files:
                    return self.send({"error": "Introuvable"}, status=404)
                file = STATIC / static_files[path]
                return self.send(file.read_bytes(), mimetypes.guess_type(file)[0] or "text/plain")
            except (ValueError, TypeError, KeyError) as exc:
                self.send({"error": str(exc)}, status=400)
            except Exception as exc:
                self.send({"error": f"Lecture impossible : {exc}"}, status=500)

        def do_POST(self):
            if not self.valid_host() or not secrets.compare_digest(self.headers.get("X-Studio-Token", ""), app.token):
                return self.send({"error": "Session invalide"}, status=403)
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                return self.send({"error": "Origine refusée"}, status=403)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 100000:
                    raise ValueError("Requête trop grande ou vide.")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Requête invalide.")
                routes = {"/api/jobs": app.start_job, "/api/corrections/preview": app.correction_preview, "/api/corrections": app.save_correction,
                          "/api/workshop/preview": app.workshop.prepare_edit, "/api/workshop/apply": app.apply_workshop,
                          "/api/workshop/undo": app.undo_workshop, "/api/workshop/retry": app.retry_workshop}
                if self.path == "/api/open-output":
                    folder = app.root / "output" / app.language(payload.get("language"))
                    if not folder.is_dir():
                        raise ValueError("Aucun dossier de sortie pour cette langue.")
                    os.startfile(folder)
                    return self.send({"ok": True})
                if self.path not in routes:
                    return self.send({"error": "Introuvable"}, status=404)
                self.send(routes[self.path](payload))
            except (ValueError, TypeError, KeyError) as exc:
                self.send({"error": str(exc)}, status=400)
            except Exception as exc:
                self.send({"error": f"Opération impossible : {exc}"}, status=500)
    return Handler


def launch_window(url):
    for base, suffix in [("ProgramFiles(x86)", "Microsoft/Edge/Application/msedge.exe"), ("ProgramFiles", "Microsoft/Edge/Application/msedge.exe"), ("ProgramFiles", "Google/Chrome/Application/chrome.exe")]:
        executable = Path(os.environ.get(base, "")) / suffix
        if executable.exists():
            subprocess.Popen([str(executable), f"--app={url}", "--window-size=1500,980"])
            return
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="FRED Studio")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    runtime = ROOT / ".fred-studio"
    if not args.no_browser:
        previous = read_json(runtime / "session.json", {})
        previous_url = previous.get("url", "")
        parsed = urlsplit(previous_url)
        if parsed.hostname == "127.0.0.1" and parsed.fragment:
            try:
                request = Request(previous_url.split("#")[0] + "api/diagnostics", headers={"X-Studio-Token": parsed.fragment})
                with urlopen(request, timeout=2) as response:
                    diagnostics = json.load(response)
                if diagnostics.get("root") == str(ROOT):
                    launch_window(previous_url)
                    return
            except Exception:
                pass
    app = Studio()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    url = f"http://127.0.0.1:{server.server_port}/#{app.token}"
    runtime.mkdir(exist_ok=True)
    atomic_json(runtime / "session.json", {"url": url, "pid": os.getpid()})
    print(f"FRED Studio : {url}", flush=True)
    if not args.no_browser:
        launch_window(url)
        def stop_when_closed():
            while True:
                time.sleep(15)
                with app.lock:
                    running = app.job and app.job["state"] == "running"
                if not running and time.time() - app.last_seen > 180:
                    server.shutdown()
                    return
        threading.Thread(target=stop_when_closed, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
