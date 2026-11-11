"""Checks every built page in dist/ at common screen widths. Run after build.py; exits 1 on any failure.

Per width: no sideways scroll; no button, text, field or link sticking out of the screen or cut inside
its box; headings fit 1 line on computers (>=1024px) and 2 lines on phones/tablets, with no single
word alone on the last line.
"""
import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

DIST = pathlib.Path(__file__).parent.parent / "dist"
WIDTHS = {320: "small phone", 344: "folded Fold", 360: "Android", 390: "iPhone", 412: "large Android",
          768: "iPad portrait", 884: "Galaxy Tab / open Fold", 1024: "small laptop", 1280: "laptop",
          1366: "common laptop", 1440: "MacBook", 1920: "Full HD"}
DESKTOP_FROM = 1024

PROBE = """(maxLines) => {
  const out = [], vw = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth > vw) out.push(`page scrolls sideways (${document.documentElement.scrollWidth}px > ${vw}px)`);
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ' "' + (el.innerText || el.value || '').trim().slice(0, 40) + '"';
  const inScroller = el => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p).overflowX; if (s === 'auto' || s === 'scroll') return true; } return false; };
  for (const el of document.querySelectorAll('a,button,input,label,h1,h2,h3,p,td,th,li,small,span,div.price,div.p-main')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden') continue;
    if ((r.left < -0.5 || r.right > vw + 0.5) && !inScroller(el)) out.push(`${name(el)} goes off screen (left ${Math.round(r.left)}, right ${Math.round(r.right)})`);
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 && getComputedStyle(el).overflowX !== 'visible') out.push(`${name(el)} text is cut inside its box`);
  }
  for (const h of document.querySelectorAll('h1,h2,h3')) {
    const range = document.createRange(), words = [];
    const walker = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
    for (let t; (t = walker.nextNode());) {
      for (const m of t.data.matchAll(/\\S+/g)) {
        range.setStart(t, m.index); range.setEnd(t, m.index + m[0].length);
        const rects = range.getClientRects(); if (rects.length) words.push(rects[rects.length - 1].top);
      }
    }
    const tops = [...new Set(words.map(Math.round))].sort((a, b) => a - b);
    const lines = tops.length, last = words.filter(t => Math.round(t) === tops[tops.length - 1]).length;
    if (lines > maxLines) out.push(`${name(h)} takes ${lines} lines (max ${maxLines})`);
    if (lines > 1 && last === 1) out.push(`${name(h)} leaves one word alone on its last line`);
  }
  return out;
}"""


def main():
    pages = sorted(DIST.rglob("*.html"))
    assert pages, "dist/ is empty: run build.py first"
    failures = 0
    # Serve dist/ over HTTP so root-relative links like /site.css load as on the live site.
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(DIST))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, label in WIDTHS.items():
            page = browser.new_page(viewport={"width": width, "height": 900})
            for f in pages:
                page.goto(base + f.relative_to(DIST).as_posix(), wait_until="networkidle")
                assert page.evaluate("[...document.styleSheets].some(s => { try { return s.cssRules.length > 0 } catch (e) { return false } })"), f"site stylesheet did not load on {f}"
                for problem in page.evaluate(PROBE, 1 if width >= DESKTOP_FROM else 2):
                    failures += 1
                    print(f"FAIL {width}px ({label}) {f.relative_to(DIST)}: {problem}")
            page.close()
        browser.close()
    server.shutdown()
    print(f"{len(pages)} page(s) x {len(WIDTHS)} widths: {failures} problem(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
