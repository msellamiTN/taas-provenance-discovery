"""Record a step-by-step TaaS Studio walkthrough video with subtitles.

Drives the real Studio UI in headless Chromium via Playwright's video
recorder, timestamps each narrated step, and writes an SRT subtitle file.
A running Studio instance is required (e.g. launched by the Colab notebook
or `uvicorn taas.studio.api:app`).

Usage:
    TAAS_STUDIO_URL=http://127.0.0.1:8000 TAAS_STUDIO_API_TOKEN=<token> \
        python scripts/record_studio_walkthrough.py

Outputs (under --out-dir, default docs/studio/reviewer/recording/):
    walkthrough-raw.webm   Playwright screen recording
    walkthrough.srt        Subtitle track aligned to the recording
    timings.json           Step start offsets used for the SRT
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

BASE = os.environ.get("TAAS_STUDIO_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ.get("TAAS_STUDIO_API_TOKEN", "")
VIEWPORT = {"width": 1440, "height": 810}


def srt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_subtitles(steps: list[dict], total: float, out: Path) -> None:
    lines = []
    for i, st in enumerate(steps, 1):
        start = st["t"]
        end = steps[i]["t"] if i < len(steps) else total
        end = min(end, total)
        if end <= start:
            end = min(start + 2.0, total)
        lines += [str(i), f"{srt_ts(start)} --> {srt_ts(end)}", st["text"], ""]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="docs/studio/reviewer/recording")
    ap.add_argument("--dwell", type=float, default=4.0,
                    help="seconds to linger on each step after actions")
    args = ap.parse_args()

    if not TOKEN:
        raise SystemExit("Set TAAS_STUDIO_API_TOKEN (never hardcode tokens).")

    out_dir = Path(args.out_dir)
    video_dir = out_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    steps: list[dict] = []
    t0 = time.monotonic()

    def mark(text: str) -> None:
        steps.append({"t": round(time.monotonic() - t0, 2), "text": text})

    def dwell(extra: float = 0.0) -> None:
        time.sleep(args.dwell + extra)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,
                                     args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport=VIEWPORT,
                                      record_video_dir=str(video_dir),
                                      record_video_size=VIEWPORT)
        page = context.new_page()
        page.set_default_timeout(60000)

        def goto(fragment: str) -> None:
            page.goto(f"{BASE}/#{fragment}", wait_until="domcontentloaded")
            page.wait_for_timeout(800)

        # -- Step 1 · connect -------------------------------------------------
        mark("1/8  Connect — open Studio, paste the API token, click Connect")
        page.goto(BASE, wait_until="domcontentloaded")
        page.locator("#token").fill(TOKEN)
        page.locator("#studio-auth-connect").click()
        page.get_by_text("Connected", exact=False).first.wait_for(timeout=30000)
        dwell(2)

        # -- Step 2 · overview -------------------------------------------------
        mark("2/8  Overview — live runtime diagnostics and platform inventory")
        goto("overview-workspace")
        page.locator("#platform-overview-refresh").click()
        page.wait_for_function(
            "() => { const el = document.querySelector('#platform-overview-status');"
            " return el && /ok|partial|error/.test(el.className); }",
            timeout=60000)
        dwell()

        # -- Step 3 · define ----------------------------------------------------
        mark("3/8  DEFINE — GoalSpec designer: templates are drafts, not validation")
        goto("goal-editor")
        try:
            page.locator("#goal-template-retry").click(timeout=5000)
            page.wait_for_timeout(2500)
        except Exception:
            pass
        try:
            btn = page.locator("#goal-template-load")
            if btn.is_enabled():
                btn.click()
                page.wait_for_timeout(1500)
        except Exception:
            pass
        dwell()

        # -- Step 4 · build -----------------------------------------------------
        mark("4/8  BUILD — Agent lifecycle: draft, validate, publish, sign, revoke")
        goto("agent-lifecycle-center")
        page.locator("#ux13-refresh").click()
        page.wait_for_timeout(3000)
        dwell()

        # -- Step 5 · discover --------------------------------------------------
        mark("5/8  DISCOVER — MCP connections: tools/list inspection, never tools/call")
        goto("mcp-studio")
        page.locator("#mcp-refresh-servers").click()
        page.wait_for_function(
            "() => { const el = document.querySelector('#mcp-server-status');"
            " return el && el.textContent.trim().length > 0; }",
            timeout=60000)
        try:
            sel = page.locator("#mcp-server-select")
            if sel.count() and sel.is_enabled() and sel.locator("option").count() > 1:
                sel.select_option(index=1)
        except Exception:
            pass
        inspect = page.locator("#mcp-inspect-server")
        if inspect.is_enabled():
            inspect.click()
            page.wait_for_function(
                "() => { const el = document.querySelector('#mcp-server-status');"
                " return el && /no tools\\/call|inspection completed/i"
                ".test(el.textContent || ''); }",
                timeout=120000)
        dwell(2)

        # -- Step 6 · discover history ------------------------------------------
        mark("6/8  DISCOVER — Tool registry & persisted discovery history")
        goto("discovery-observability")
        page.locator("#obs-refresh-runs").click()
        page.wait_for_function(
            "() => { const el = document.querySelector('#obs-runs-status');"
            " return el && el.textContent.trim().length > 0; }",
            timeout=60000)
        dwell()

        # -- Step 7 · verify ------------------------------------------------------
        mark("7/8  VERIFY — Audit timeline: load events, verify the hash chain")
        goto("ux19-governance-audit-timeline")
        page.locator("#ux19-load").click()
        page.wait_for_function(
            "() => { const el = document.querySelector('#ux19-status');"
            " return el && el.textContent.trim().length > 0; }",
            timeout=60000)
        page.locator("#ux19-verify").click()
        page.wait_for_function(
            "() => { const el = document.querySelector('#ux19-governance-audit-timeline');"
            " return el && /chain_valid|chain valid/i.test(el.textContent || ''); }",
            timeout=60000)
        dwell(2)

        # -- Step 8 · operate / manage ---------------------------------------------
        mark("8/8  OPERATE & MANAGE — runtime diagnostics; unsupported data says UNAVAILABLE")
        goto("runtime-observability")
        try:
            page.locator("#runtime-refresh").click(timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        dwell(3)

        video = page.video
        context.close()
        webm = video.path() if video else None
        browser.close()

    assert webm is not None
    total = time.monotonic() - t0

    (out_dir / "timings.json").write_text(json.dumps(
        {"base_url": BASE, "steps": steps, "approx_total_s": round(total, 2)},
        indent=2), encoding="utf-8")
    build_subtitles(steps, total, out_dir / "walkthrough.srt")
    print("RAW VIDEO:", webm)
    print("SRT:", out_dir / "walkthrough.srt")
    print("STEPS:")
    for s in steps:
        print(f"  {s['t']:7.1f}s  {s['text']}")


if __name__ == "__main__":
    main()
