"""Headless tests for our local app. Run with .venv-studio Python + playwright."""
import json
import sys
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from studio.server import Studio, make_handler
from playwright.sync_api import sync_playwright, expect


def main():
    app = Studio(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    folder = ROOT / ".fred-studio/qa"
    folder.mkdir(parents=True, exist_ok=True)
    failures = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/#{app.token}")
            expect(page.get_by_role("heading", name="Chaque carte compte.")).to_be_visible()
            expect(page.locator(".hero-card")).to_have_count(3)
            page.locator(".hero-card").first.wait_for(state="visible")
            page.evaluate("Promise.all(Array.from(document.images).map(i=>i.decode().catch(()=>{})))")
            page.screenshot(path=str(folder / "01-accueil.png"), full_page=True)
            page.get_by_role("button", name="Explorer le catalogue", exact=True).click()
            page.get_by_role("searchbox").fill("Ariel")
            expect(page.locator(".card-tile").first).to_be_visible()
            assert page.locator(".card-tile").count() > 0
            page.screenshot(path=str(folder / "02-catalogue.png"), full_page=True)
            page.locator(".card-tile").first.click()
            expect(page.get_by_role("dialog")).to_be_visible()
            page.screenshot(path=str(folder / "03-carte.png"))
            page.get_by_role("tab", name="Atelier de correction").click()
            page.locator("#correction-field").select_option("name")
            page.locator("#before").fill("Ariel")
            page.locator("#after").fill("Ariel test")
            page.get_by_role("button", name="Prévisualiser", exact=True).click()
            expect(page.locator("#save-correction")).to_be_enabled()
            expect(page.locator("#correction-preview")).to_contain_text("Ariel test")
            page.screenshot(path=str(folder / "04-atelier.png"))
            page.get_by_role("button", name="Fermer la fiche").click()
            page.get_by_role("searchbox").fill("aucune_carte_000")
            expect(page.get_by_role("heading", name="Aucune carte dans cette sélection")).to_be_visible()
            page.get_by_role("button", name="Réinitialiser", exact=True).click()
            expect(page.locator(".card-tile")).to_have_count(48)
            page.get_by_role("button", name="Vue en liste").click()
            expect(page.locator(".card-row")).to_have_count(48)
            page.locator("#language").select_option("en")
            expect(page.locator("#nav-count")).to_have_text("3\u202f327")
            page.get_by_role("button", name="Exports", exact=True).click()
            expect(page.locator(".export-row").first).to_be_visible()
            with page.expect_download() as download:
                page.locator(".export-row a").first.click()
            assert download.value.suggested_filename == "allCards.json"
            page.get_by_role("button", name="Paramètres", exact=True).click()
            expect(page.locator(".live-tag")).to_have_text("DISPONIBLE")
            page.get_by_role("button", name="Traitements", exact=True).click()
            page.locator("#job-action").select_option("verify")
            page.locator("#job-ids").fill("1")
            with page.expect_response(lambda response: response.url.endswith('/api/jobs') and response.request.method == 'POST') as started:
                page.get_by_role("button", name="Lancer le traitement", exact=True).click()
            assert started.value.status == 200
            job_id = started.value.json()["id"]
            page.wait_for_function("id => state.job?.id === id && state.job.state !== 'running'", arg=job_id)
            expect(page.locator("#job-state")).to_have_text("TERMINÉ", timeout=30000)
            expect(page.locator("#job-log")).to_contain_text("finished after")
            page.screenshot(path=str(folder / "05-traitements.png"), full_page=True)
            page.locator("#language").select_option("de")
            page.get_by_role("button", name="Catalogue", exact=False).first.click()
            expect(page.get_by_role("heading", name="Aucune carte dans cette sélection")).to_be_visible()
            page.locator("#language").select_option("fr")
            page.get_by_role("button", name="Vue d’ensemble", exact=True).click()
            page.evaluate("document.querySelector('#toast').hidePopover()")
            for width, height in [(1100, 850), (800, 900), (430, 900)]:
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Overflow at {width}"
                page.screenshot(path=str(folder / f"06-accueil-{width}.png"), full_page=True)
            assert not failures, failures
            browser.close()
        print(json.dumps({"result": "passed", "screenshots": str(folder), "consoleErrors": failures}, indent=2))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
