"""Daily price check. Reads each vendor's official pricing page, compares the lines that contain a
dollar or euro sign with the last saved snapshot, and when they change opens a GitHub issue for a human to
review. It never edits data/*.json: prices on the site change only after someone approves.

Snapshots live in snapshots/<tool>.txt. First run only saves them.
Env: GROQ_API_KEY (optional, adds a plain-language summary), GITHUB_ACTIONS + GH_TOKEN (to open issues).
"""
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent.parent
SNAP = ROOT / "snapshots"
GROQ_MODEL = "openai/gpt-oss-20b"
# body.innerText skips shadow DOM; Make renders its plans in <code-island> shadow roots, so add their text after the body's.
# shortcut: only shadow roots attached to light-DOM elements, nested ones are skipped; walk them recursively if a page needs it.
PAGE_TEXT_JS = """() => [document.body, ...[...document.querySelectorAll('*')].filter(e => e.shadowRoot)
  .flatMap(e => [...e.shadowRoot.children])].map(e => e.innerText || '').join('\\n')"""


def price_lines(text):
    """Visible lines that mention a dollar or euro amount, whitespace-normalised, order kept, duplicates dropped."""
    seen, out = set(), []
    text = re.sub(r"([$€])\s*\n\s*", r"\1", text)  # some pages put "$"/"€" and the amount on separate lines
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if ("$" in line or "€" in line) and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def diff(old, new):
    return [l for l in difflib.unified_diff(old, new, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]


def groq_summary(tool, changes, data):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return ""
    prompt = (f"These lines changed on {tool}'s official pricing page ('-' removed, '+' added):\n" + "\n".join(changes) +
              f"\n\nOur site currently shows this data:\n{json.dumps(data.get('plans') or data.get('components'), indent=1)[:4000]}"
              "\n\nIn at most 6 short bullet points: which prices or limits changed, and which values in our data "
              "would need updating. Quote numbers exactly from the lines above. If the change is not about prices, say so.")
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps({"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # the summary is a convenience; the raw diff is still reported
        return f"(Groq summary unavailable: {exc})"


def open_issue(title, body):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print(f"--- would open issue: {title}\n{body}\n---")
        return
    subprocess.run(["gh", "issue", "create", "--title", title, "--body", body], check=True)


def main():
    assert diff(["$1 a", "$2 b"], ["$1 a", "$3 b"]) == ["-$2 b", "+$3 b"]
    assert price_lines("x\n $5  /mo \nno\n$5 /mo") == ["$5 /mo"]
    assert price_lines("Pro\n$\n40\n/mo") == ["$40"]
    assert price_lines("Starter\n€\n24\n/mo\nfree") == ["€24"]
    assert price_lines("€60 /mo\n$28 /mo") == ["€60 /mo", "$28 /mo"]
    SNAP.mkdir(exist_ok=True)
    tools = [(f, json.loads(f.read_text())) for f in sorted((ROOT / "data").glob("*.json"))]
    tools = [(f, d) for f, d in tools if isinstance(d, dict) and d.get("source_url")]
    changed = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for f, d in tools:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            try:
                page.goto(d["source_url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)  # pricing pages render prices with JavaScript
                lines = price_lines(page.evaluate(PAGE_TEXT_JS))
            except Exception as exc:
                open_issue(f"Price check failed: {d['tool']}", f"Could not read {d['source_url']}: {exc}")
                continue
            finally:
                page.close()
            snap = SNAP / f"{d['slug']}.txt"
            if not lines:
                open_issue(f"Price check found no prices: {d['tool']}",
                           f"{d['source_url']} returned no lines with a $ or € sign. The page may have changed layout.")
                continue
            if snap.exists():
                changes = diff(snap.read_text().splitlines(), lines)
                if changes:
                    changed += 1
                    summary = groq_summary(d["tool"], changes, d)
                    body = (f"The pricing page {d['source_url']} changed since the last check.\n\n"
                            + (f"**Summary (Groq, check before trusting):**\n{summary}\n\n" if summary else "")
                            + "**Changed lines:**\n```diff\n" + "\n".join(changes)[:6000] + "\n```\n\n"
                            f"Update data/{f.name} only after checking the page yourself.")
                    open_issue(f"{d['tool']} pricing page changed", body)
            snap.write_text("\n".join(lines) + "\n")
            print(f"{d['tool']}: {len(lines)} price lines")
        browser.close()
    print(f"{changed} page(s) changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
