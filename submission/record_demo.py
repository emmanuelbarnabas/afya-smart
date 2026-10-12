"""Rekodi demo video ya Afya Smart (Playwright walkthrough → webm → mp4).

Run:  .venv-tools/bin/python submission/record_demo.py
Matokeo: submission/AfyaSmart_Demo.mp4 (~3-4 dakika, 1280x720)

Mfululizo: title card → landing (/demo) → USSD simulator (triage + booking +
facility search + health guide) → nurse dashboard (fair queue + call next +
clinician feedback) → patient app (live position + booking) → closing card.
"""
import pathlib
import subprocess
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent.parent
SUB = ROOT / "submission"
TITLES = SUB / "assets" / "titles"
BASE = "http://127.0.0.1:8000"
WEBM = SUB / "AfyaSmart_Demo.webm"
MP4 = SUB / "AfyaSmart_Demo.mp4"

PHONE = "+255712345678"


def seed_queue() -> None:
    """Weka wagonjwa kwenye foleni ili dashboard ionyeshe foleni hai."""
    import json
    import urllib.request

    def post(url: str, payload: dict) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    names = ["Asha Juma", "Baraka Msigwa", "Neema Kessy", "Juma Mkumbo"]
    for i, name in enumerate(names):
        try:
            p = post(f"{BASE}/api/v1/intake",
                     {"full_name": name, "facility_id": 1, "preferred_language": "sw"})
            post(f"{BASE}/api/v1/intake/{p['id']}/queue", {})
        except Exception as e:  # tayari ipo / network
            print("seed skip:", name, e)
    print("Queue seeded:", len(names))


def ussd(session, keys_after_dial: list[str], pause: float = 2.6, read: float = 1.2):
    """Piga USSD, kisha bonyeza namba kwa mpangilio (kila kimoja hufuatiwa na send)."""
    session.click("#btn-call")           # dial
    session.wait_for_timeout(3000)        # soma skrini ya karibu
    for k in keys_after_dial:
        session.click(f'.key[data-k="{k}"]')
        session.wait_for_timeout(500)
        session.click("#btn-call")       # tuma jibu
        session.wait_for_timeout(int(pause * 1000))
        session.wait_for_timeout(int(read * 1000))


def main() -> None:
    seed_queue()
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(SUB / ".recordings"),
            record_video_size={"width": 1280, "height": 720},
            locale="sw-TZ",
        )
        page = ctx.new_page()

        # 1) Intro card
        page.goto((TITLES / "intro.html").resolve().as_uri())
        page.wait_for_timeout(7000)

        # 2) Agenda card
        page.goto((TITLES / "agenda.html").resolve().as_uri())
        page.wait_for_timeout(7000)

        # 3) Landing page — picha halisi, icon, huduma
        page.goto(f"{BASE}/demo")
        page.wait_for_timeout(4000)
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(3000)
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(3000)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(3500)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(3000)
        page.mouse.wheel(0, -3000)
        page.wait_for_timeout(2000)

        # 4) USSD simulator
        page.goto(f"{BASE}/ussd-demo")
        page.wait_for_timeout(2000)
        # badilisha namba ya simu ya demo
        page.fill("#phone", PHONE)
        page.wait_for_timeout(500)
        # lugha: Kiswahili
        ussd(page, ["1"])
        # 1 = Kagua dalili zako (triage — mtu mzima, homa siku 3-6, maumivu makali)
        #    0=Hapana kupumua shida, 1=Ndiyo fahamu, 0=Hapana damu, 1=homa 3-6,
        #    2=maumivu kati, 0=mtu mzima  → ROUTINE/URGENT kutoka model
        ussd(page, ["1", "0", "1", "0", "1", "2", "0"], pause=3.0)
        page.wait_for_timeout(4000)
        # chagua nafasi ya miadi kama slot menu imeonekana (1)
        ussd(page, ["1"], pause=3.0)
        page.wait_for_timeout(4000)
        # session mpya: 6 = Angalia miadi yangu
        ussd(page, ["1", "6"], pause=3.0)
        page.wait_for_timeout(4000)
        # session mpya: 4 = Tafuta hospitali (eneo → kituo → hali ya foleni)
        ussd(page, ["1", "4", "1", "1", "1"], pause=2.6)
        page.wait_for_timeout(3500)
        # session mpya: 5 = Mwongozo wa afya → Malaria
        ussd(page, ["1", "5", "2"], pause=2.6)
        page.wait_for_timeout(3500)
        # session mpya: 0 = Toka
        ussd(page, ["1", "0"], pause=2.0)
        page.wait_for_timeout(2000)

        # 5) Nurse dashboard — foleni hai + call next + maamuzi
        page.goto(f"{BASE}/dashboard")
        page.wait_for_timeout(6000)
        # Ita mgonjwa wa kwanza (kitufe: "Ita Mgonjwa")
        call_btn = page.locator("button", has_text="Ita Mgonjwa").first
        if call_btn.count():
            call_btn.click()
            page.wait_for_timeout(4500)
        # Rekodi maamuzi ya clinician kwa mgonjwa wa kwanza
        fb = page.locator("button", has_text="clinician").first
        if fb.count():
            fb.click()
            page.wait_for_timeout(2000)
            opt = page.locator(".feedback-options button").first
            if opt.count():
                opt.click()
                page.wait_for_timeout(3000)
        # Angalia Analytics
        an = page.locator("nav.page-nav button", has_text="Analytics").first
        if an.count():
            an.click()
            page.wait_for_timeout(5000)
            page.mouse.wheel(0, 500)
            page.wait_for_timeout(3000)
        # Kumbusho
        rm = page.locator("nav.page-nav button", has_text="Kumbusho").first
        if rm.count():
            rm.click()
            page.wait_for_timeout(4000)

        # 6) Patient app — nafasi + miadi + USSD simulator ndani ya app
        page.goto(f"{BASE}/app")
        page.wait_for_timeout(5000)
        bk = page.locator("nav button", has_text="Miadi").first
        if bk.count():
            bk.click()
            page.wait_for_timeout(4000)
        us = page.locator("nav button", has_text="USSD").first
        if us.count():
            us.click()
            page.wait_for_timeout(3500)

        # 7) Architecture diagram
        page.goto((SUB / "assets" / "architecture.svg").resolve().as_uri())
        page.set_viewport_size({"width": 1600, "height": 1000})
        page.wait_for_timeout(8000)

        # 8) Closing card
        page.set_viewport_size({"width": 1280, "height": 720})
        page.goto((TITLES / "closing.html").resolve().as_uri())
        page.wait_for_timeout(7000)

        dur = time.time() - t0
        ctx.close()      # video inahifadhiwa hapa
        browser.close()
    print(f"Video ya ~{dur:.0s}s" if False else f"Video ya ~{dur:.0f}s imehifadhiwa")

    # webm → mp4 (H.264, inafaa kwa hackathon upload)
    clips = sorted((SUB / ".recordings").glob("*.webm"))
    if not clips:
        raise SystemExit("Hakuna video iliyorekodiwa")
    clips[-1].replace(WEBM)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(WEBM),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(MP4)],
        check=True, capture_output=True,
    )
    print("MP4:", MP4)


if __name__ == "__main__":
    main()
