"""Builds the static site into dist/. Prices come only from data/*.json, never from an LLM."""
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
SITE = "https://aistackprices.com"
e = html.escape


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


def fmt_date(iso):
    import datetime
    return datetime.date.fromisoformat(iso).strftime("%-d %B %Y")


# Plain string (not an f-string) so CSS braces need no escaping.
CSS = """
:root{--ink:#16233a;--muted:#5a6678;--line:#d9e0e8;--mist:#f0f4f8;--paper:#fff;--cobalt:#2350c8;--tag:#f6cf45;--tag-ink:#3d3000}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 "Schibsted Grotesk",system-ui,sans-serif}
a{color:var(--cobalt);text-underline-offset:3px}
a:focus-visible,input:focus-visible,button:focus-visible{outline:3px solid var(--cobalt);outline-offset:3px}
.wrap{max-width:980px;margin:0 auto;padding:0 20px}
.top{border-bottom:1px solid var(--line)}
.top .wrap{display:flex;justify-content:space-between;align-items:center;gap:16px;min-height:60px;flex-wrap:wrap}
.brand{font-weight:800;color:var(--ink);text-decoration:none;font-size:18px;letter-spacing:-.01em}
.brand span{display:inline-block;background:var(--tag);color:var(--tag-ink);padding:0 6px;margin-right:6px;border-radius:3px}
.checked{color:var(--muted);font-size:14px}
h1{font-size:clamp(34px,6vw,56px);line-height:1.04;letter-spacing:-.03em;font-weight:800;margin:44px 0 12px}
h1,h2,h3{text-wrap:balance}
.lede{color:var(--muted);font-size:19px;max-width:58ch;margin:0 0 28px}
h2{font-size:26px;letter-spacing:-.02em;line-height:1.2;margin:56px 0 12px}
h3{font-size:18px;margin:28px 0 4px}
p{max-width:68ch}
.calc{background:var(--ink);color:#fff;border-radius:14px;padding:28px;display:grid;grid-template-columns:1.1fr 1fr;gap:28px;align-items:center}
.calc label{display:block;font-weight:600;margin-bottom:10px}
.need{display:flex;gap:14px;align-items:center}
.need input[type=range]{flex:1;accent-color:var(--tag)}
.need input[type=number]{width:96px;font:inherit;font-weight:600;padding:6px 8px;border-radius:6px;border:0}
.bill{display:inline-flex;margin-top:18px;border:1px solid #ffffff55;border-radius:999px;padding:3px}
.bill button{font:inherit;font-size:15px;background:none;color:#fff;border:0;border-radius:999px;padding:6px 16px;cursor:pointer;white-space:nowrap}
.bill button[aria-pressed=true]{background:#fff;color:var(--ink);font-weight:600}
.answer{border-left:1px solid #ffffff33;padding-left:28px}
.answer .price{font-size:clamp(48px,8vw,72px);font-weight:800;letter-spacing:-.04em;line-height:1}
.answer .price small{font-size:20px;font-weight:600;letter-spacing:0;margin-left:4px}
.answer .plan{margin:10px 0 0;color:#dfe6f2}
.hint{color:var(--muted);font-size:14px;margin-top:10px}
table{width:100%;border-collapse:collapse;margin-top:8px}
th{text-align:left;font-size:14px;font-weight:600;color:var(--muted);padding:0 12px 10px;border-bottom:2px solid var(--ink)}
td{padding:16px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr.fit td{background:#fff8d6}
tr.fit td:first-child{box-shadow:inset 5px 0 0 var(--tag)}
.pname{font-weight:800;font-size:19px}
.p-main,.answer .price{font-variant-numeric:tabular-nums}.p-main{font-weight:800;font-size:22px;letter-spacing:-.02em}
.p-sub{color:var(--muted);font-size:14px}
.bar{height:10px;background:var(--mist);border-radius:5px;margin:6px 0 4px;min-width:120px}
.bar i{display:block;height:100%;background:var(--cobalt);border-radius:5px}
.feat{font-size:15px;color:var(--muted)}td:nth-child(3){min-width:200px}
.cta{display:inline-block;margin:28px 0 8px;background:var(--cobalt);color:#fff;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:8px}
.note{color:var(--muted);font-size:14px}
.faq{border-top:1px solid var(--line);margin-top:8px}
.faq h3{margin-top:24px}
footer{border-top:1px solid var(--line);margin-top:64px;padding:24px 0 40px}
.list{list-style:none;padding:0;margin:0}
.list li{border-bottom:1px solid var(--line)}
.list a{display:block;padding:18px 0;font-weight:600;font-size:20px;text-decoration:none}
@media (max-width:720px){
 .calc{grid-template-columns:1fr;padding:22px}
 .answer{border-left:0;border-top:1px solid #ffffff33;padding:22px 0 0}
 thead{display:none}
 table,tbody,tr,td{display:block}
 tr{border-bottom:1px solid var(--line);padding:14px 0}
 td{border:0;padding:2px 12px}
 tr.fit{background:#fff8d6;box-shadow:inset 5px 0 0 var(--tag)}
 tr.fit td{background:none}
 tr.fit td:first-child{box-shadow:none}
}
@media (prefers-reduced-motion:no-preference){tr td{transition:background-color .25s}}
"""

FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;600;800&display=swap" '
        'rel="stylesheet">')


def page(title, desc, path, body, checked="", schema=None):
    ld = f'<script type="application/ld+json">{json.dumps(schema)}</script>' if schema else ""
    stamp = f'<span class="checked">Prices checked {fmt_date(checked)}</span>' if checked else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{path}">
{FONT}<style>{CSS}</style>{ld}</head><body>
<header class="top"><div class="wrap"><a class="brand" href="/"><span>$</span>AI Stack Prices</a>{stamp}</div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap note"><p>AI Stack Prices is independent and not affiliated with any company listed. Prices are copied from each vendor's official pricing page on the date shown. Confirm on the vendor's site before you buy.</p></div></footer>
</body></html>"""


def price_cell(p):
    if not p["monthly"]:
        return '<div class="p-main">$0</div>'
    return (f'<div class="p-main">${p["annual_per_month"]}<span class="p-sub">/mo yearly</span></div>'
            f'<div class="p-sub">${p["monthly"]}/mo on monthly billing</div>')


def pricing_page(d):
    plans = d["plans"]
    tool = e(d["tool"])
    link = d["affiliate_url"] or d["source_url"]
    star = "*" if d["affiliate_url"] else ""
    disclosure = ('<p class="note">* Affiliate link: we may earn a commission if you buy through it, '
                  'at no extra cost to you.</p>') if d["affiliate_url"] else ""
    top = max(p["message_credits"] for p in plans)
    rows = "".join(f"""<tr data-plan="{e(p['name'])}">
<td><div class="pname">{e(p['name'])}</div></td>
<td>{price_cell(p)}</td>
<td>{p['message_credits']:,} message credits/mo<div class="bar"><i style="width:{max(2, round(p['message_credits'] / top * 100))}%"></i></div>
<div class="p-sub">{p['integration_credits']:,} integration credits/mo</div></td>
<td class="feat">{e(', '.join(p['features']))}</td></tr>""" for p in plans)
    paid = [p for p in plans if p["monthly"]]
    lo, hi = paid[0], paid[-1]
    faq = [
        (f"How much does {d['tool']} cost?",
         f"{d['tool']} has a free plan. Paid plans run from ${lo['monthly']}/month ({lo['name']}) to "
         f"${hi['monthly']}/month ({hi['name']}) on monthly billing, or ${lo['annual_per_month']} to "
         f"${hi['annual_per_month']} per month billed annually."),
        (f"Is {d['tool']} free?",
         f"Yes. The Free plan gives {plans[0]['message_credits']} message credits and "
         f"{plans[0]['integration_credits']} integration credits per month, for up to 5 apps."),
        ("Is annual billing worth it?",
         "Annual billing costs 20% less than monthly and adds: " + "; ".join(d["annual_only_features"]) +
         ". You pay for the full year up front."),
        (f"What is a {d['tool']} credit?",
         f"{d['tool']} describes credits as your monthly usage allowance for AI messages and integration "
         "actions. Each plan includes message credits and integration credits separately, and usage per "
         "action varies with the AI model you select."),
    ]
    faq_html = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faq)
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    calc_data = json.dumps([{k: p[k] for k in ("name", "monthly", "annual_per_month", "message_credits")}
                            for p in plans])
    body = f"""
<h1>{tool} pricing and real costs</h1>
<p class="lede">What you will actually pay: every {tool} plan, its credits, and the cheapest one for how much you build. Taken from the <a href="{e(d['source_url'])}">official pricing page</a>.</p>
<section class="calc" aria-label="{tool} cost calculator">
 <div>
  <label for="need">AI message credits you use each month</label>
  <div class="need"><input id="range" type="range" min="0" max="{top}" step="5" value="150" aria-label="Message credits per month">
  <input id="need" type="number" min="0" value="150"></div>
  <div class="bill" role="group" aria-label="Billing period">
   <button type="button" id="yr" aria-pressed="true">Yearly</button>
   <button type="button" id="mo" aria-pressed="false">Monthly</button>
  </div>
 </div>
 <div class="answer" aria-live="polite"><div class="price" id="price"></div><p class="plan" id="plan"></p></div>
</section>
<p class="hint">{tool} says credit use varies by action and AI model, so treat this as an estimate.</p>
<h2>All {tool} plans</h2>
<table><thead><tr><th>Plan</th><th>Price</th><th>Credits</th><th>Includes</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="note">Enterprise pricing is custom, by quote from {tool} sales.</p>
<a class="cta" href="{e(link)}" rel="nofollow sponsored">See {tool}'s current plans{star}</a>
{disclosure}
<h2>Questions people ask</h2>
<div class="faq">{faq_html}</div>
<script>
const P={calc_data},R=document.getElementById('range'),N=document.getElementById('need'),Y=document.getElementById('yr'),M=document.getElementById('mo');
let yearly=true;
function run(){{const n=Math.max(0,+N.value||0),k=yearly?'annual_per_month':'monthly',
f=P.filter(p=>p.message_credits>=n).sort((a,b)=>a[k]-b[k])[0];
document.querySelectorAll('tr[data-plan]').forEach(r=>r.classList.toggle('fit',!!f&&r.dataset.plan===f.name));
document.getElementById('price').innerHTML=f?'$'+f[k]+'<small>/month</small>':'Enterprise';
document.getElementById('plan').textContent=f?(f.name+' plan, $'+(f[k]*12).toLocaleString('en-US')+' a year'+(yearly?' paid up front':' if you stay 12 months')+'.'):'More than the largest plan. Ask {tool} sales for a quote.';}}
R.oninput=()=>{{N.value=R.value;run();}};N.oninput=()=>{{R.value=N.value;run();}};
function bill(y){{yearly=y;Y.setAttribute('aria-pressed',y);M.setAttribute('aria-pressed',!y);run();}}
Y.onclick=()=>bill(true);M.onclick=()=>bill(false);run();
</script>"""
    title = f"{d['tool']} Pricing {d['checked'][:4]}: Plans, Credits & Cost Calculator"
    desc = (f"{d['tool']} pricing checked {fmt_date(d['checked'])}: Free, then ${lo['monthly']}-${hi['monthly']}/mo "
            f"(or ${lo['annual_per_month']}-${hi['annual_per_month']}/mo yearly). Credits per plan and a calculator.")
    return page(title, desc, f"/{d['slug']}/", body, d["checked"], schema)


def main():
    pages = []
    for f in sorted((ROOT / "data").glob("*.json")):
        d = json.loads(f.read_text())
        self_check(d)
        out = DIST / d["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pricing_page(d))
        pages.append(d)
    links = "".join(f'<li><a href="/{d["slug"]}/">{e(d["tool"])} pricing</a></li>' for d in pages)
    (DIST / "index.html").write_text(page(
        "AI Stack Prices: Real Costs of AI App Builders and Voice Agents",
        "Sourced, dated pricing for AI app builders and voice-agent platforms, with cost calculators.", "/",
        f'<h1>What AI tools cost</h1><p class="lede">Plans, credits and calculators for AI app builders '
        f'and voice agents, copied from each official pricing page with the date we checked.</p>'
        f'<ul class="list">{links}</ul>'))
    print(f"built {len(pages)} pricing page(s) into {DIST}")


if __name__ == "__main__":
    main()
