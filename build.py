"""Builds the static site into dist/. Prices come only from data/*.json, never from an LLM."""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
SITE = "https://aistackprices.com"


def cheapest(plans, credits_needed, annual):
    """Cheapest plan whose monthly message credits cover the need; None if no plan does."""
    key = "annual_per_month" if annual else "monthly"
    fits = [p for p in plans if p["message_credits"] >= credits_needed]
    return min(fits, key=lambda p: p[key]) if fits else None


def self_check(d):
    plans = d["plans"]
    for p in plans:
        assert p["annual_per_month"] <= p["monthly"], p["name"]
    assert cheapest(plans, 0, False)["name"] == "Free"
    assert cheapest(plans, 101, True)["name"] == "Builder"
    assert cheapest(plans, 10**9, True) is None


def page(title, desc, path, body, schema=None):
    ld = f'<script type="application/ld+json">{json.dumps(schema)}</script>' if schema else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{SITE}{path}">
<style>
body{{font:16px/1.6 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:0 16px;color:#1a1a1a;background:#fff}}
table{{border-collapse:collapse;width:100%;min-width:640px;font-size:15px}}th,td{{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f4f4f4}}.wrap{{overflow-x:auto}}.note{{color:#555;font-size:14px}}
.calc{{background:#f7f7f7;border:1px solid #ddd;padding:16px;border-radius:8px}}input[type=number]{{font-size:16px;width:120px}}.calc label{{display:block;margin:6px 0}}
a{{color:#0645ad}}
</style>{ld}</head><body>
<header><p><a href="/">AI Stack Prices</a></p></header>
{body}
<footer class="note"><p>Independent site. Not affiliated with any company listed. Prices are copied from each vendor's official pricing page on the date shown; always confirm on the vendor's site before buying.</p></footer>
</body></html>"""


def pricing_page(d):
    e = html.escape
    plans = d["plans"]
    link = d["affiliate_url"] or d["source_url"]
    disclosure = ('<p class="note">* Affiliate link: we may earn a commission if you buy through it, '
                  'at no extra cost to you.</p>') if d["affiliate_url"] else ""
    star = "*" if d["affiliate_url"] else ""
    rows = "".join(
        f"<tr><td>{e(p['name'])}</td><td>${p['monthly']}</td><td>${p['annual_per_month']} "
        f"(${p['annual_per_month'] * 12:,}/yr)</td><td>{p['message_credits']:,}</td>"
        f"<td>{p['integration_credits']:,}</td><td>{e(', '.join(p['features']))}</td></tr>"
        for p in plans)
    paid = [p for p in plans if p["monthly"]]
    lo, hi = paid[0], paid[-1]
    tool = e(d["tool"])
    faq = [
        (f"How much does {tool} cost?",
         f"{tool} has a free plan. Paid plans run from ${lo['monthly']}/month ({lo['name']}) to "
         f"${hi['monthly']}/month ({hi['name']}) on monthly billing, or ${lo['annual_per_month']}"
         f"–${hi['annual_per_month']}/month billed annually."),
        (f"Is {tool} free?",
         f"Yes. The Free plan gives {plans[0]['message_credits']} message credits and "
         f"{plans[0]['integration_credits']} integration credits per month, for up to 5 apps."),
        ("Is annual billing worth it?",
         "Annual billing costs 20% less than monthly and adds: " + e("; ".join(d["annual_only_features"])) +
         ". You pay the full year up front."),
    ]
    faq_html = "".join(f"<h3>{q}</h3><p>{a}</p>" for q, a in faq)
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": html.unescape(q),
         "acceptedAnswer": {"@type": "Answer", "text": html.unescape(a)}} for q, a in faq]}
    calc_data = json.dumps([{k: p[k] for k in ("name", "monthly", "annual_per_month", "message_credits")}
                            for p in plans])
    body = f"""<main>
<h1>{tool} Pricing ({d['checked'][:4]}): Every Plan, Credits and Real Monthly Cost</h1>
<p class="note">Prices checked on {d['checked']} from the <a href="{e(d['source_url'])}">official {tool} pricing page</a>.</p>
<div class="wrap"><table>
<tr><th>Plan</th><th>Monthly billing</th><th>Annual billing (per month)</th><th>Message credits / mo</th><th>Integration credits / mo</th><th>Includes</th></tr>
{rows}</table></div>
<p>Enterprise pricing is custom (quote from sales).</p>
<h2>Which plan do you need? Cost calculator</h2>
<div class="calc">
<label>AI message credits you use per month: <input id="need" type="number" min="0" value="150"></label>
<label><input id="annual" type="checkbox" checked> Billed annually</label>
<p id="out" aria-live="polite"></p>
</div>
<p class="note">{tool} says exact credit usage varies by action and by the AI model you select, so treat this as an estimate.</p>
<h2>What is a credit?</h2>
<p>{tool} describes credits as your monthly usage allowance for AI messages and integration actions. Each plan lists message credits and integration credits separately.</p>
<h2>FAQ</h2>
{faq_html}
<p><a href="{e(link)}" rel="nofollow sponsored">See current {tool} plans{star}</a></p>
{disclosure}
</main>
<script>
const P={calc_data};
function run(){{const n=+document.getElementById('need').value||0,a=document.getElementById('annual').checked,
k=a?'annual_per_month':'monthly',f=P.filter(p=>p.message_credits>=n).sort((x,y)=>x[k]-y[k])[0],o=document.getElementById('out');
o.textContent=f?`Cheapest fit: ${{f.name}} at $${{f[k]}}/month ($${{(f[k]*12).toLocaleString('en-US')}}/year)${{a?'':' on monthly billing'}}.`
:'More than the largest plan: ask {tool} sales about Enterprise.';}}
document.getElementById('need').oninput=run;document.getElementById('annual').onchange=run;run();
</script>"""
    title = f"{d['tool']} Pricing {d['checked'][:4]}: Plans, Credits & Cost Calculator"
    desc = (f"{d['tool']} pricing checked {d['checked']}: Free, then ${lo['monthly']}–${hi['monthly']}/mo "
            f"(or ${lo['annual_per_month']}–${hi['annual_per_month']}/mo yearly). Credits per plan and a calculator.")
    return page(title, desc, f"/{d['slug']}/", body, schema)


def main():
    pages = []
    for f in sorted((ROOT / "data").glob("*.json")):
        d = json.loads(f.read_text())
        self_check(d)
        out = DIST / d["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pricing_page(d))
        pages.append(d)
    links = "".join(f'<li><a href="/{d["slug"]}/">{html.escape(d["tool"])} pricing</a></li>' for d in pages)
    (DIST / "index.html").write_text(page(
        "AI Stack Prices: Real Costs of AI App Builders and Voice Agents",
        "Up-to-date, sourced pricing for AI app builders and voice-agent platforms.", "/",
        f"<main><h1>AI Stack Prices</h1><p>Sourced, dated pricing for AI tools.</p><ul>{links}</ul></main>"))
    print(f"built {len(pages)} pricing page(s) into {DIST}")


if __name__ == "__main__":
    main()
