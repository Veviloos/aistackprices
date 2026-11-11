"""Builds the static site into dist/. Prices come only from data/*.json, never from an LLM.

Styling: Tailwind classes in this file are compiled once into static/site.css (see README),
so visitors download a small CSS file instead of the Tailwind runtime.

Data: each data/<tool>.json is a pricing page of kind "credits" (plans with credit allowances)
or "usage" (per-minute pricing). data/compare.json lists comparison pages between two tools.
"""
import datetime
import html
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
SITE = "https://aistackprices.com"
e = html.escape


def cheapest(plans, credits_needed, annual):
    """Cheapest option whose monthly credits cover the need; None if no option does."""
    key = "annual_per_month" if annual else "monthly"
    fits = [p for p in plans if p["credits"] >= credits_needed]
    return min(fits, key=lambda p: p[key]) if fits else None


def calc_options(d):
    return d.get("tiers") or [p for p in d["plans"] if "credits" in p]


def self_check(d):
    if d["kind"] == "usage":
        lo, hi, typ = d["per_min_low"], d["per_min_high"], d.get("per_min_typical")
        assert 0 <= lo < hi, d["tool"]
        assert typ is None or lo <= typ <= hi, d["tool"]
        assert all(fee >= 0 for _, fee in d["fees"]), d["tool"]
        return
    for p in d["plans"]:
        if "monthly" in p and "annual_per_month" in p:
            assert p["annual_per_month"] <= p["monthly"], p["name"]
    assert sum(p.get("popular", False) for p in d["plans"]) <= 1
    opts = sorted(calc_options(d), key=lambda p: p["credits"])
    assert len(opts) >= 2, d["tool"]
    for a, b in zip(opts, opts[1:]):
        assert a["credits"] < b["credits"] and a["monthly"] < b["monthly"], (a["name"], b["name"])
    # With prices rising with credits, the cheapest fit is the smallest option that covers the need.
    assert cheapest(opts, 0, False) is opts[0]
    assert cheapest(opts, opts[0]["credits"] + 1, False) is opts[1]
    assert cheapest(opts, opts[-1]["credits"], False) is opts[-1]
    assert cheapest(opts, opts[-1]["credits"] + 1, False) is None


def fmt_date(iso):
    return datetime.date.fromisoformat(iso).strftime("%-d %B %Y")


FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet">')


def page(title, desc, path, body, schema=None):
    ld = f'<script type="application/ld+json">{json.dumps(schema)}</script>' if schema else ""
    return f"""<!doctype html>
<html lang="en" class="bg-[#090A0F]"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{path}">
{FONT}<link rel="stylesheet" href="/site.css">{ld}</head>
<body class="min-h-screen bg-[#090A0F] font-[Geist,system-ui,sans-serif] text-slate-300 antialiased">
<div aria-hidden="true" class="pointer-events-none fixed inset-x-0 top-0 h-[480px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(99,102,241,0.18),transparent)]"></div>
<header class="relative border-b border-slate-800/80">
 <div class="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
  <a href="/" class="flex items-center gap-2 rounded font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400">
   <span class="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-indigo-500 to-violet-500 text-sm">$</span>AI Stack Prices</a>
 </div>
</header>
<main class="relative mx-auto max-w-6xl px-5">{body}</main>
<footer class="relative mt-24 border-t border-slate-800/80">
 <p class="mx-auto max-w-6xl px-5 py-10 text-sm text-slate-500">AI Stack Prices is independent and not affiliated with any company listed. Prices are copied from each vendor's official pricing page on the date shown. Confirm on the vendor's site before you buy.</p>
</footer>
</body></html>"""


def plan_card(p, link, monthly_only=False):
    pop = p.get("popular", False)
    ring = ("bg-gradient-to-b from-indigo-500 via-violet-500 to-indigo-500/20 shadow-[0_0_40px_-8px_rgba(139,92,246,0.55)]"
            if pop else "bg-slate-800")
    badge = ('<span class="whitespace-nowrap rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-medium text-indigo-300">'
             'Most popular</span>') if pop else ""
    if p["monthly"] and monthly_only:
        a = p["annual_per_month"]
        note = f"or ${a}/month billed yearly" if a != p["monthly"] else "billed monthly"
        price = (f'<p class="mt-4 flex items-baseline gap-1"><span class="text-4xl font-semibold tracking-tight text-white tabular-nums">${p["monthly"]}</span>'
                 f'<span class="text-sm text-slate-400">/month</span></p><p class="mt-1 text-xs text-slate-500">{e(note)}</p>')
    elif p["monthly"]:
        price = (f'<p class="mt-4 flex items-baseline gap-1"><span class="text-4xl font-semibold tracking-tight text-white tabular-nums" '
                 f'data-annual="{p["annual_per_month"]}" data-monthly="{p["monthly"]}">${p["annual_per_month"]}</span>'
                 f'<span class="text-sm text-slate-400">/month</span></p>'
                 f'<p class="mt-1 text-xs text-slate-500" data-note data-annual-note="billed yearly, ${p["annual_per_month"] * 12:,}/year" '
                 f'data-monthly-note="billed monthly">billed yearly, ${p["annual_per_month"] * 12:,}/year</p>')
    else:
        price = ('<p class="mt-4 flex items-baseline gap-1"><span class="text-4xl font-semibold tracking-tight text-white">$0</span>'
                 '<span class="text-sm text-slate-400">/month</span></p><p class="mt-1 text-xs text-slate-500">no payment needed</p>')
    feats = "".join(f'<li class="flex gap-2"><span aria-hidden="true" class="text-indigo-400">✓</span>{e(f)}</li>'
                    for f in p["features"])
    rows = "".join(f'<div class="flex justify-between gap-3"><dt class="text-slate-400">{e(k)}</dt>'
                   f'<dd class="text-right font-medium text-white tabular-nums">{e(v)}</dd></div>' for k, v in p["rows"])
    btn = ("bg-gradient-to-r from-indigo-500 to-violet-500 text-white hover:from-indigo-400 hover:to-violet-400"
           if pop else "border border-slate-700 text-slate-200 hover:border-slate-500 hover:text-white")
    return f"""<article data-plan="{e(p['name'])}" class="rounded-2xl p-px {ring}">
 <div class="flex h-full flex-col rounded-[15px] bg-slate-900/80 p-6 backdrop-blur-md">
  <div class="flex items-center justify-between gap-2"><h3 class="text-lg font-semibold text-white">{e(p['name'])}</h3>{badge}</div>
  {price}
  <dl class="mt-5 space-y-1 border-y border-slate-800 py-4 text-sm">{rows}</dl>
  <ul class="mt-4 flex-1 space-y-2 text-sm text-slate-300">{feats}</ul>
  <a href="{e(link)}" rel="nofollow sponsored" class="mt-6 block rounded-lg px-4 py-2.5 text-center text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 {btn}">Choose {e(p['name'])}</a>
 </div>
</article>"""


H1 = "bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text font-semibold tracking-tight text-balance text-transparent"
H2 = "text-center text-3xl font-semibold tracking-tight text-balance text-white"
PANEL = "rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-md"
CTA = ("inline-block rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-5 py-2.5 font-medium text-white "
       "hover:from-indigo-400 hover:to-violet-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400")
LINK = "text-indigo-300 underline decoration-indigo-500/40 underline-offset-4 hover:text-white"
NUM = ("rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-right font-medium text-white tabular-nums "
       "focus-visible:outline-2 focus-visible:outline-indigo-400")
SEG = ("rounded-md px-3 py-1.5 whitespace-nowrap text-slate-400 focus-visible:outline-2 focus-visible:outline-indigo-400 "
       "aria-pressed:bg-indigo-500 aria-pressed:text-white")
TABLE = "w-full text-left text-sm"
TH = "py-3 pr-4 font-normal text-slate-400"
TD = "py-3 font-medium text-white tabular-nums"


def link_of(d):
    return d["affiliate_url"] or d["source_url"]


def hero(checked, h1, h1_size, lede):
    return f"""
<section class="pt-16 pb-10 text-center sm:pt-24">
 <p class="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/70 px-3.5 py-1 text-xs text-slate-300 backdrop-blur-md">
  <span class="relative flex h-2 w-2"><span class="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 motion-safe:animate-ping"></span><span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-400"></span></span>
  Prices checked {checked}</p>
 <h1 class="mx-auto mt-6 {H1} {h1_size}">{e(h1)}</h1>
 <p class="mx-auto mt-5 max-w-2xl text-lg text-pretty text-slate-400">{lede}</p>
</section>"""


def faq_block(faq):
    """FAQ section plus its FAQPage JSON-LD."""
    items = "".join(f"""<details class="group rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 backdrop-blur-md">
<summary class="flex cursor-pointer list-none justify-between gap-4 rounded font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400">{e(q)}<span aria-hidden="true" class="text-slate-500 transition-transform group-open:rotate-45">+</span></summary>
<p class="mt-3 text-sm leading-relaxed text-slate-400">{e(a)}</p></details>""" for q, a in faq)
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return f"""
<section aria-labelledby="faq-h" class="mx-auto mt-24 max-w-3xl">
 <h2 id="faq-h" class="{H2}">Questions people ask</h2>
 <div class="mt-8 space-y-3">{items}</div>
</section>""", schema


def trust(tools, cta=True):
    """The "How we get these numbers" box for one or more tools."""
    if len(tools) == 1:
        d = tools[0]
        src = f"{e(d['tool'])}'s official pricing page and note the date we checked it: {fmt_date(d['checked'])}."
    else:
        names = " and ".join(f"{e(d['tool'])}'s" for d in tools)
        dates = ", ".join(f"{e(d['tool'])} {fmt_date(d['checked'])}" for d in tools)
        src = f"{names} official pricing pages and note the dates we checked them: {dates}."
    disclosure = ("Some links on this page are affiliate links: if you buy through them we may earn a commission, "
                  "at no extra cost to you. It never changes the prices shown." if any(d["affiliate_url"] for d in tools) else
                  "We don't earn anything from the links on this page.")
    btn = (f'<a href="{e(link_of(tools[0]))}" rel="nofollow sponsored" class="mt-5 {CTA}">See {e(tools[0]["tool"])}\'s current pricing</a>'
           if cta else "")
    return f"""
<section class="mx-auto mt-16 max-w-3xl {PANEL} p-6 text-sm text-slate-400">
 <p><span class="font-medium text-slate-200">How we get these numbers.</span> We copy each price from {src} {disclosure}</p>
 {btn}
</section>"""


def source_lede(d):
    return f'{e(d["lede"])} Copied from the <a class="{LINK}" href="{e(d["source_url"])}">official pricing page</a>.'


def credits_page(d):
    plans, opts = d["plans"], calc_options(d)
    tool = e(d["tool"])
    link = link_of(d)
    checked = fmt_date(d["checked"])
    monthly_only = d.get("monthly_only", False)
    top = max(p["credits"] for p in opts)
    paid = [p for p in plans if p["monthly"]]
    lo, hi = paid[0], paid[-1]
    faq_html, schema = faq_block(d["faq"])
    calc_data = json.dumps([{"name": p["name"], "label": p["name"] if "tiers" in d else p["name"] + " plan",
                             "credits": p["credits"], "monthly": p["monthly"],
                             "annual_per_month": p.get("annual_per_month", p["monthly"])} for p in opts])
    cards = "".join(plan_card(p, link, monthly_only) for p in plans)
    cols = "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5" if len(plans) >= 5 else "sm:grid-cols-2 lg:grid-cols-3"
    toggle = "" if monthly_only else f"""
  <div role="group" aria-label="Billing period" class="inline-flex rounded-lg border border-slate-700 bg-slate-950/60 p-1 text-sm">
   <button type="button" id="yr" aria-pressed="true" class="{SEG}">{e(d["yearly_label"])}</button>
   <button type="button" id="mo" aria-pressed="false" class="{SEG}">Monthly</button>
  </div>"""
    if "tiers" in d:
        hint = "The tier that fits your usage is highlighted in the table below as you move the calculator."
        rows = "".join(f'<tr data-tier="{e(t["name"])}" class="border-t border-slate-800">'
                       f'<th scope="row" class="py-2.5 pr-4 pl-3 font-normal">{e(t["name"])}</th>'
                       f'<td class="py-2.5 pr-4 tabular-nums">{t["credits"]:,}</td>'
                       f'<td class="py-2.5 pr-3 text-right font-medium text-white tabular-nums">${t["monthly"]:,}/mo</td></tr>'
                       for t in d["tiers"])
        tiers = f"""
 <div class="mx-auto mt-12 max-w-2xl {PANEL} p-3 sm:p-5">
  <h3 class="px-3 pt-2 text-lg font-semibold text-white">{e(d["tiers_title"])}</h3>
  <table class="mt-3 {TABLE}">
   <thead class="text-xs text-slate-500"><tr><th scope="col" class="py-2 pr-4 pl-3 font-normal">Tier</th><th scope="col" class="py-2 pr-4 font-normal">Credits</th><th scope="col" class="py-2 pr-3 text-right font-normal">Monthly price</th></tr></thead>
   <tbody class="text-slate-300">{rows}</tbody>
  </table>
 </div>"""
    else:
        hint = "The plan that fits your usage gets a green outline as you move the calculator."
        tiers = ""
    body = hero(checked, f"{d['tool']} pricing and real costs", "text-4xl sm:text-5xl lg:text-6xl", source_lede(d)) + f"""

<section aria-labelledby="calc-h" class="mx-auto max-w-4xl {PANEL} p-6 shadow-[0_0_60px_-20px_rgba(99,102,241,0.45)] sm:p-8">
 <div class="flex flex-wrap items-center justify-between gap-4">
  <h2 id="calc-h" class="text-xl font-semibold text-white">Cost calculator</h2>{toggle}
 </div>
 <div class="mt-8 grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
  <div>
   <div class="flex items-baseline justify-between gap-3">
    <label for="range" class="text-sm text-slate-400">{e(d["calc_label"])}</label>
    <input id="need" type="number" min="0" inputmode="numeric" value="150" aria-label="{e(d["calc_label"])}" class="w-24 {NUM}">
   </div>
   <input id="range" type="range" min="0" max="{top}" step="5" value="150" class="mt-4 w-full accent-indigo-500">
   <div class="mt-1 flex justify-between text-xs text-slate-500 tabular-nums"><span>0</span><span>{top:,}</span></div>
  </div>
  <div aria-live="polite" class="md:min-w-56 md:text-right">
   <p class="text-sm text-slate-400">Estimated cost</p>
   <p id="price" class="mt-1 text-5xl font-semibold tracking-tight text-white tabular-nums"></p>
   <p id="plan" class="mt-2 text-sm text-slate-400"></p>
  </div>
 </div>
 <p class="mt-6 text-xs text-slate-500">{e(d["calc_note"])}</p>
</section>

<section aria-labelledby="plans-h" class="mt-24">
 <h2 id="plans-h" class="{H2}">All {tool} plans</h2>
 <p class="mt-3 text-center text-slate-400">{hint}</p>
 <div class="mt-10 grid gap-5 {cols}">{cards}</div>{tiers}
 <p class="mx-auto mt-6 max-w-3xl text-center text-sm text-slate-500">{e(d["after_plans"])}</p>
</section>
{faq_html}
{trust([d])}

<script>
const P={calc_data},R=document.getElementById('range'),N=document.getElementById('need'),Y=document.getElementById('yr'),M=document.getElementById('mo');
let yearly={'false' if monthly_only else 'true'};
const HI=['bg-indigo-500/15','text-white'];
function run(){{const n=Math.max(0,+N.value||0),k=yearly?'annual_per_month':'monthly',
f=P.filter(p=>p.credits>=n).sort((a,b)=>a[k]-b[k])[0];
document.querySelectorAll('article[data-plan]').forEach(c=>{{const on=!!f&&c.dataset.plan===f.name;['outline-2','outline-emerald-400','outline-offset-4'].forEach(x=>c.classList.toggle(x,on));}});
document.querySelectorAll('tr[data-tier]').forEach(r=>{{const on=!!f&&r.dataset.tier===f.name;HI.forEach(x=>r.classList.toggle(x,on));r.toggleAttribute('data-picked',on);}});
document.querySelectorAll('[data-annual]').forEach(s=>s.textContent='$'+s.dataset[yearly?'annual':'monthly']);
document.querySelectorAll('[data-note]').forEach(s=>s.textContent=s.dataset[yearly?'annualNote':'monthlyNote']);
document.getElementById('price').textContent=f?'$'+f[k].toLocaleString('en-US')+'/mo':'Custom';
document.getElementById('plan').textContent=f?(f.label+', $'+(f[k]*12).toLocaleString('en-US')+' a year'+(yearly?' paid up front.':' if you stay 12 months.')):'Above the largest plan. Ask {tool} sales for a quote.';}}
R.oninput=()=>{{N.value=R.value;run();}};N.oninput=()=>{{R.value=Math.min(+N.value||0,{top});run();}};
function bill(y){{yearly=y;Y.setAttribute('aria-pressed',y);M.setAttribute('aria-pressed',!y);run();}}
if(Y){{Y.onclick=()=>bill(true);M.onclick=()=>bill(false);}}run();
</script>"""
    title = f"{d['tool']} Pricing {d['checked'][:4]}: Plans, Credits & Cost Calculator"
    free = "Free, then " if any(not p["monthly"] for p in plans) else ""
    desc = (f"{d['tool']} pricing checked {checked}: {free}${lo['monthly']}-${hi['monthly']}/mo "
            f"(or ${lo['annual_per_month']}-${hi['annual_per_month']}/mo yearly). Credits per plan and a calculator.")
    return page(title, desc, f"/{d['slug']}/", body, schema)


def usage_page(d):
    tool = e(d["tool"])
    checked = fmt_date(d["checked"])
    lo, hi, typ = d["per_min_low"], d["per_min_high"], d.get("per_min_typical")
    faq_html, schema = faq_block(d["faq"])
    fees = "".join(f'<button type="button" data-fee="{fee}" aria-pressed="{"true" if i == 0 else "false"}" class="{SEG}">'
                   f'{e(name)}{f", ${fee:,}/mo" if fee else ""}</button>' for i, (name, fee) in enumerate(d["fees"]))
    fees = (f'<div role="group" aria-label="Monthly package" class="inline-flex flex-wrap rounded-lg border border-slate-700 '
            f'bg-slate-950/60 p-1 text-sm">{fees}</div>') if fees else ""
    comps = "".join(f'<tr class="border-t border-slate-800"><th scope="row" class="{TH}">{e(k)}</th>'
                    f'<td class="{TD} text-right">{e(v)}</td></tr>' for k, v in d["components"])
    incl = "".join(f'<li class="flex gap-2"><span aria-hidden="true" class="text-indigo-400">✓</span>{e(x)}</li>'
                   for x in d["includes"])
    calc = json.dumps({"lo": lo, "hi": hi, "typ": typ, "typLabel": d.get("typical_label", ""),
                       "fee": d["fees"][0][1] if d["fees"] else 0})
    body = hero(checked, f"{d['tool']} pricing and real costs", "text-4xl sm:text-5xl lg:text-6xl", source_lede(d)) + f"""

<section aria-labelledby="calc-h" class="mx-auto max-w-4xl {PANEL} p-6 shadow-[0_0_60px_-20px_rgba(99,102,241,0.45)] sm:p-8">
 <div class="flex flex-wrap items-center justify-between gap-4">
  <h2 id="calc-h" class="text-xl font-semibold text-white">Cost calculator</h2>{fees}
 </div>
 <div class="mt-8 grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
  <div>
   <div class="flex items-baseline justify-between gap-3">
    <label for="range" class="text-sm text-slate-400">Call minutes each month</label>
    <input id="need" type="number" min="0" step="100" inputmode="numeric" value="1000" aria-label="Call minutes per month" class="w-28 {NUM}">
   </div>
   <input id="range" type="range" min="0" max="20000" step="100" value="1000" class="mt-4 w-full accent-indigo-500">
   <div class="mt-1 flex justify-between text-xs text-slate-500 tabular-nums"><span>0</span><span>20,000</span></div>
  </div>
  <div aria-live="polite" class="md:min-w-64 md:text-right">
   <p class="text-sm text-slate-400">Estimated cost</p>
   <p id="price" class="mt-1 text-4xl font-semibold tracking-tight text-balance text-white tabular-nums sm:text-5xl"></p>
   <p id="typ" class="mt-2 text-sm text-slate-300"></p>
   <p id="plan" class="mt-1 text-sm text-slate-400"></p>
  </div>
 </div>
</section>

<section aria-labelledby="comp-h" class="mx-auto mt-16 max-w-4xl">
 <div class="{PANEL} p-6 sm:p-8">
  <h2 id="comp-h" class="text-xl font-semibold text-balance text-white">{e(d["components_title"])}</h2>
  <table class="mt-4 {TABLE}"><tbody>{comps}</tbody></table>
  <ul class="mt-6 space-y-2 border-t border-slate-800 pt-6 text-sm text-slate-300">{incl}</ul>
  <p class="mt-6 text-xs text-slate-500">{e(d["calc_note"])}</p>
 </div>
</section>
{faq_html}
{trust([d])}

<script>
const C={calc},R=document.getElementById('range'),N=document.getElementById('need');
let fee=C.fee;
const $=v=>'$'+Math.round(v).toLocaleString('en-US');
function run(){{const n=Math.max(0,+N.value||0),a=$(n*C.lo+fee),b=$(n*C.hi+fee);
document.getElementById('price').textContent=(a===b?a:a+' to '+b)+'/mo';
document.getElementById('typ').textContent=C.typ===null?'':C.typLabel+': '+$(n*C.typ+fee)+'/mo';
document.getElementById('plan').textContent=n.toLocaleString('en-US')+' minutes at $'+C.lo+' to $'+C.hi+' a minute'+(fee?', plus $'+fee+' a month.':'.');}}
R.oninput=()=>{{N.value=R.value;run();}};N.oninput=()=>{{R.value=Math.min(+N.value||0,20000);run();}};
document.querySelectorAll('[data-fee]').forEach(b=>b.onclick=()=>{{fee=+b.dataset.fee;document.querySelectorAll('[data-fee]').forEach(x=>x.setAttribute('aria-pressed',x===b));run();}});
run();
</script>"""
    title = f"{d['tool']} Pricing {d['checked'][:4]}: Cost per Minute & Calculator"
    desc = (f"{d['tool']} pricing checked {checked}: ${lo:g} to ${hi:g} per minute. "
            "What makes up the price and a monthly cost calculator.")
    return page(title, desc, f"/{d['slug']}/", body, schema)


def compare_page(c, a, b):
    rows = "".join(
        f'<tr class="border-t border-slate-800 max-sm:block max-sm:py-3"><th scope="row" class="{TH} max-sm:block max-sm:py-1 max-sm:font-medium max-sm:text-slate-200 sm:w-1/4">{e(k)}</th>'
        + "".join(f'<td class="py-3 pr-4 align-top text-slate-300 max-sm:block max-sm:py-1"><span class="text-slate-500 sm:hidden">{e(d["tool"])}: </span>'
                  f'{e(d["compare"].get(k, "Not listed"))}</td>' for d in (a, b))
        + "</tr>" for k in a["compare"])
    cards = "".join(f"""<article class="{PANEL} p-6">
  <h3 class="text-lg font-semibold text-white">{e(d['tool'])}</h3>
  <p class="mt-1 text-xs text-slate-500">Prices checked {fmt_date(d['checked'])}</p>
  <div class="mt-5 flex flex-wrap items-center gap-x-5 gap-y-3 text-sm">
   <a href="{e(link_of(d))}" rel="nofollow sponsored" class="{CTA}">See {e(d['tool'])}'s current pricing</a>
   <a href="/{e(d['slug'])}/" class="{LINK}">{e(d['tool'])} pricing and calculator</a>
  </div>
 </article>""" for d in (a, b))
    names = f"{a['tool']} vs {b['tool']}"
    checked = fmt_date(min(a["checked"], b["checked"]))
    lede = (f'{e(a["tool"])} and {e(b["tool"])} pricing side by side, copied from the official pricing pages of '
            f'<a class="{LINK}" href="{e(a["source_url"])}">{e(a["tool"])}</a> and <a class="{LINK}" href="{e(b["source_url"])}">{e(b["tool"])}</a>.')
    body = hero(checked, f"{names} pricing", "text-4xl sm:text-5xl lg:text-6xl", lede) + f"""

<section aria-labelledby="cmp-h" class="mx-auto max-w-4xl {PANEL} p-6 sm:p-8">
 <h2 id="cmp-h" class="text-xl font-semibold text-white">Side by side</h2>
 <table class="mt-4 {TABLE}">
  <thead class="text-xs text-slate-500 max-sm:sr-only"><tr><th scope="col" class="py-2 pr-4 font-normal">&nbsp;</th><th scope="col" class="py-2 pr-4 font-normal">{e(a['tool'])}</th><th scope="col" class="py-2 pr-4 font-normal">{e(b['tool'])}</th></tr></thead>
  <tbody>{rows}</tbody>
 </table>
</section>

<section class="mx-auto mt-10 grid max-w-4xl gap-5 md:grid-cols-2">{cards}</section>
{trust([a, b], cta=False)}"""
    title = f"{names} Pricing {max(a['checked'], b['checked'])[:4]}: Plans and Costs Side by Side"
    desc = f"{names} pricing side by side, copied from each official pricing page. Checked {checked}."
    return page(title, desc, f"/{c['slug']}/", body)


def index_page(tools, comps):
    item = "flex flex-wrap justify-between gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 font-medium text-white hover:border-indigo-500/60"
    links = "".join(f'<li><a class="{item}" href="/{d["slug"]}/">{e(d["tool"])} pricing<span class="text-sm text-slate-500">checked {fmt_date(d["checked"])}</span></a></li>' for d in tools)
    vs = "".join(f'<li><a class="{item}" href="/{c["slug"]}/">{e(a["tool"])} vs {e(b["tool"])}<span class="text-sm text-slate-500">pricing side by side</span></a></li>' for c, a, b in comps)
    return page(
        "AI Stack Prices: Real Costs of AI App Builders and Voice Agents",
        "Sourced, dated pricing for AI app builders and voice-agent platforms, with cost calculators.", "/",
        f'<section class="mx-auto max-w-3xl pt-16 sm:pt-24"><h1 class="{H1} text-4xl sm:text-6xl">What AI tools cost</h1>'
        f'<p class="mt-5 text-lg text-slate-400">Plans, credits and calculators for AI app builders and voice agents, copied from each official pricing page with the date we checked.</p>'
        f'<h2 class="mt-12 text-xl font-semibold text-white">Pricing pages</h2><ul class="mt-4 space-y-3">{links}</ul>'
        f'<h2 class="mt-12 text-xl font-semibold text-white">Comparisons</h2><ul class="mt-4 space-y-3">{vs}</ul></section>')


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST)
    out = {}  # url path -> (html, lastmod)
    tools = {}
    for f in sorted((ROOT / "data").glob("*.json")):
        if f.stem == "compare":
            continue
        d = json.loads(f.read_text())
        self_check(d)
        tools[f.stem] = d
        out[f"/{d['slug']}/"] = ((credits_page if d["kind"] == "credits" else usage_page)(d), d["checked"])
    comps = []
    for c in json.loads((ROOT / "data" / "compare.json").read_text()):
        a, b = tools[c["a"]], tools[c["b"]]
        comps.append((c, a, b))
        out[f"/{c['slug']}/"] = (compare_page(c, a, b), max(a["checked"], b["checked"]))
    out["/"] = (index_page(list(tools.values()), comps), max(d["checked"] for d in tools.values()))
    for path, (doc, _) in out.items():
        target = DIST / path.strip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc)
    urls = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{m}</lastmod></url>" for p, (_, m) in sorted(out.items()))
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                      f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    print(f"built {len(out)} page(s) into {DIST}: {', '.join(sorted(out))}")


if __name__ == "__main__":
    main()
