"""Builds the static site into dist/. Prices come only from data/*.json, never from an LLM.

Styling: Tailwind classes in this file are compiled once into static/site.css (see README),
so visitors download a small CSS file instead of the Tailwind runtime.

Data: each data/<tool>.json is a pricing page of kind "credits" (plans with credit allowances)
or "usage" (per-minute pricing). data/compare.json lists comparison pages between two tools.
"""
import datetime
import hashlib
import html
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / "dist"
SITE = "https://aistackprices.com"
e = html.escape
CHROME = {}  # nav links and stylesheet version, filled in main()


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
    NAV, YEAR = CHROME["nav"], datetime.date.today().year
    CSS_V = CHROME["css_v"]  # changes whenever site.css changes, so browsers drop their cached copy
    ld = f'<script type="application/ld+json">{json.dumps(schema)}</script>' if schema else ""
    return f"""<!doctype html>
<html lang="en" class="bg-[#090A0F]"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{path}">
{FONT}<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" href="/favicon-96.png" sizes="96x96" type="image/png"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="stylesheet" href="/site.css?v={CSS_V}">{ld}</head>
<body class="min-h-screen bg-[#090A0F] font-[Geist,system-ui,sans-serif] text-slate-300 antialiased">
<div aria-hidden="true" class="pointer-events-none fixed inset-x-0 top-0 h-[480px] bg-[radial-gradient(60%_60%_at_50%_0%,rgba(99,102,241,0.18),transparent)]"></div>
<header class="sticky top-0 z-30 border-b border-slate-800/80 bg-[#090A0F]/70 backdrop-blur-md">
 <div class="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
  <a href="/" class="flex shrink-0 items-center gap-2 rounded font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400">
   <img src="/mark.svg" alt="" width="28" height="28" class="h-7 w-7">AI Stack Prices</a>
  <nav aria-label="Main" class="hidden items-center gap-6 text-sm text-slate-400 md:flex">{NAV}</nav>
  <details class="relative md:hidden">
   <summary aria-label="Menu" class="grid h-10 w-10 cursor-pointer list-none place-items-center rounded-lg border border-slate-700 text-slate-200 hover:border-slate-500 focus-visible:outline-2 focus-visible:outline-indigo-400 [&::-webkit-details-marker]:hidden">
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 4.5h14M2 9h14M2 13.5h14"/></svg></summary>
   <nav aria-label="Main" class="absolute right-0 mt-2 flex w-56 flex-col rounded-xl border border-slate-800 bg-slate-950 p-2 text-sm text-slate-300 shadow-2xl shadow-black/60 [&>a]:rounded-lg [&>a]:px-3 [&>a]:py-2.5 [&>a:hover]:bg-slate-800/70" onclick="if(event.target.closest('a'))this.parentElement.open=false">{NAV}</nav>
  </details>
 </div>
</header>
<main class="relative mx-auto max-w-6xl px-5">{body}</main>
<p class="relative mt-16 px-5 pb-4 text-center text-[11px] text-slate-500 min-[340px]:text-xs sm:text-sm">Independent. Prices copied from official pricing pages.</p>
<footer class="relative border-t border-slate-800/80">
 <p class="px-5 py-6 text-center text-sm text-slate-400">&copy; {YEAR} AI Stack Prices</p>
</footer>
</body></html>"""


def plan_card(p, link, monthly_only=False, cur="$"):
    pop = p.get("popular", False)
    ring = ("bg-gradient-to-b from-indigo-500 via-violet-500 to-indigo-500/20 shadow-[0_0_40px_-8px_rgba(139,92,246,0.55)]"
            if pop else "bg-slate-800")
    badge = ('<span class="whitespace-nowrap rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-medium text-indigo-300">'
             'Most popular</span>') if pop else ""
    if "price" in p:  # usage-based plans publish a text price, e.g. "$29/month" or "Custom"
        price = (f'<p class="mt-4 text-3xl font-semibold tracking-tight text-balance text-white tabular-nums">{e(p["price"])}</p>'
                 f'<p class="mt-1 text-xs text-slate-500">{e(p.get("price_note", ""))}</p>')
    elif p["monthly"] and monthly_only:
        a = p["annual_per_month"]
        note = f"or {cur}{a}/month billed yearly" if a != p["monthly"] else "billed monthly"
        price = (f'<p class="mt-4 flex items-baseline gap-1"><span class="text-4xl font-semibold tracking-tight text-white tabular-nums">{cur}{p["monthly"]}</span>'
                 f'<span class="text-sm text-slate-400">/month</span></p><p class="mt-1 text-xs text-slate-500">{e(note)}</p>')
    elif p["monthly"]:
        price = (f'<p class="mt-4 flex items-baseline gap-1"><span class="text-4xl font-semibold tracking-tight text-white tabular-nums" '
                 f'data-annual="{p["annual_per_month"]}" data-monthly="{p["monthly"]}">{cur}{p["annual_per_month"]}</span>'
                 f'<span class="text-sm text-slate-400">/month</span></p>'
                 f'<p class="mt-1 text-xs text-slate-500" data-note data-annual-note="billed yearly, {cur}{p["annual_per_month"] * 12:,}/year" '
                 f'data-monthly-note="billed monthly">billed yearly, {cur}{p["annual_per_month"] * 12:,}/year</p>')
    else:
        price = (f'<p class="mt-4 flex items-baseline gap-1"><span class="text-4xl font-semibold tracking-tight text-white">{cur}0</span>'
                 '<span class="text-sm text-slate-400">/month</span></p><p class="mt-1 text-xs text-slate-500">no payment needed</p>')
    feats = "".join(f'<li class="flex gap-2"><span aria-hidden="true" class="text-indigo-400">✓</span>{e(f)}</li>'
                    for f in p["features"])
    rows = "".join(f'<div class="flex justify-between gap-3"><dt class="text-slate-400">{e(k)}</dt>'
                   f'<dd class="text-right font-medium text-white tabular-nums">{e(v)}</dd></div>' for k, v in p.get("rows", []))
    btn = ("bg-gradient-to-r from-indigo-500 to-violet-500 text-white hover:from-indigo-400 hover:to-violet-400"
           if pop else "border border-slate-700 text-slate-200 hover:border-slate-500 hover:text-white")
    return f"""<article data-plan="{e(p['name'])}" class="rounded-2xl p-px {ring}">
 <div class="flex h-full flex-col rounded-[15px] bg-slate-900/80 p-6 backdrop-blur-md">
  <div class="flex items-center justify-between gap-2"><h3 class="text-lg font-semibold text-white">{e(p['name'])}</h3>{badge}</div>
  {price}
  {f'<dl class="mt-5 space-y-1 border-y border-slate-800 py-4 text-sm">{rows}</dl>' if rows else '<div class="mt-5 border-t border-slate-800"></div>'}
  <ul class="mt-4 flex-1 space-y-2 text-sm text-slate-300">{feats}</ul>
  <a href="{e(link)}" rel="nofollow sponsored" class="mt-6 block rounded-lg px-4 py-2.5 text-center text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 {btn}">{e(p.get('cta', 'Choose ' + p['name']))}</a>
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


def hero(checked, h1, h1_size, lede, extra=""):
    return f"""
<section class="pt-12 pb-10 text-center sm:pt-20">
 <p class="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/70 px-3.5 py-1 text-xs text-slate-300 backdrop-blur-md">
  <span class="relative flex h-2 w-2"><span class="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 motion-safe:animate-ping"></span><span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-400"></span></span>
  Prices checked {checked}</p>
 <h1 class="mx-auto mt-6 {H1} {h1_size}">{e(h1)}</h1>
 <p class="mx-auto mt-5 max-w-2xl text-lg text-pretty text-slate-400">{lede}</p>{extra}
</section>"""


def compare_btn(d):
    """Outline button from a tool page to its comparison page (set in main from data/compare.json)."""
    if not d.get("compare_with"):
        return ""
    slug, other = d["compare_with"]
    return (f'\n <a href="/{slug}/" class="mt-8 inline-block rounded-lg border border-slate-700 bg-slate-900/60 px-5 py-2.5 text-sm font-medium text-slate-200 '
            f'hover:border-indigo-400/60 hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-400">Compare {e(d["tool"])} vs {e(other)}</a>')


def faq_block(faq):
    """FAQ section plus its FAQPage JSON-LD."""
    items = "".join(f"""<details class="group rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 backdrop-blur-md">
<summary class="flex cursor-pointer list-none justify-between gap-4 rounded font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400">{e(q)}<span aria-hidden="true" class="text-slate-500 transition-transform group-open:rotate-45">+</span></summary>
<p class="mt-3 text-sm leading-relaxed text-slate-400">{e(a)}</p></details>""" for q, a in faq)
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return f"""
<section aria-labelledby="faq-h" class="mx-auto mt-16 max-w-3xl">
 <h2 id="faq-h" class="{H2}">Questions people ask</h2>
 <div class="mt-8 space-y-3">{items}</div>
</section>""", schema


def page_end(tools, cta=True):
    """End of a tool page: an optional button to the vendor, plus the affiliate disclosure once a page has affiliate links.
    How prices are collected is explained once, on the homepage."""
    btn = (f'<a href="{e(link_of(tools[0]))}" rel="nofollow sponsored" class="{CTA}">See {e(tools[0]["tool"])}\'s current pricing</a>'
           if cta else "")
    note = ('<p class="mt-4 text-xs text-slate-500">Some links on this page are affiliate links: if you buy through them we may '
            'earn a commission, at no extra cost to you. It never changes the prices shown.</p>'
            if any(d["affiliate_url"] for d in tools) else "")
    return f'<section class="mt-16 text-center">{btn}{note}</section>' if btn or note else ""


def source_lede(d):
    return e(d["lede"])  # the source is named once, in the "How we get these numbers" box at the end


def credits_page(d):
    plans, opts = d["plans"], calc_options(d)
    tool = e(d["tool"])
    link = link_of(d)
    checked = fmt_date(d["checked"])
    monthly_only = d.get("monthly_only", False)
    cur = d.get("currency", "$")
    top = max(p["credits"] for p in opts)
    paid = [p for p in plans if p.get("monthly")]  # "Custom" plans have a text price, no monthly
    lo, hi = paid[0], paid[-1]
    faq_html, schema = faq_block(d["faq"])
    calc_data = json.dumps([{"name": p["name"], "label": p["name"] if "tiers" in d else p["name"] + " plan",
                             "credits": p["credits"], "monthly": p["monthly"],
                             "annual_per_month": p.get("annual_per_month", p["monthly"])} for p in opts])
    cards = "".join(plan_card(p, link, monthly_only, cur) for p in plans)
    # Centered rows so a short last row sits in the middle, never hanging on the left.
    cols = ("*:w-full sm:*:w-[calc(50%-0.625rem)] lg:*:w-[calc(33.333%-0.834rem)] xl:*:w-[calc(20%-1rem)]" if len(plans) >= 5
            else "*:w-full sm:*:w-[calc(50%-0.625rem)] lg:*:w-[calc(25%-0.9375rem)]" if len(plans) == 4  # 2+2, then 4 in a row
            else "*:w-full md:*:w-[calc(33.333%-0.834rem)]")
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
                       f'<td class="py-2.5 pr-3 text-right font-medium text-white tabular-nums">{cur}{t["monthly"]:,}/mo</td></tr>'
                       for t in d["tiers"])
        tiers = f"""
 <div class="mx-auto mt-12 max-w-2xl {PANEL} p-3 sm:p-5">
  <h3 class="px-3 pt-2 text-lg font-semibold text-white">{e(d["tiers_title"])}</h3>
  <table class="mt-3 {TABLE}">
   <thead class="text-xs text-slate-500"><tr><th scope="col" class="py-2 pr-4 pl-3 font-normal">Tier</th><th scope="col" class="py-2 pr-4 font-normal">{e(d.get("unit_label", "Credits"))}</th><th scope="col" class="py-2 pr-3 text-right font-normal">Monthly price</th></tr></thead>
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

<section aria-labelledby="plans-h" class="mt-16">
 <h2 id="plans-h" class="{H2}">All {tool} plans</h2>
 <p class="mt-3 text-center text-slate-400">{hint}</p>
 <div class="mt-10 flex flex-wrap justify-center gap-5 {cols}">{cards}</div>{tiers}
 <p class="mx-auto mt-6 max-w-3xl text-center text-sm text-slate-500">{e(d["after_plans"])}</p>
 <div class="text-center">{compare_btn(d)}</div>
</section>
{faq_html}
{page_end([d], cta=False)}

<script>
const P={calc_data},C={json.dumps(cur)},R=document.getElementById('range'),N=document.getElementById('need'),Y=document.getElementById('yr'),M=document.getElementById('mo');
let yearly={'false' if monthly_only else 'true'};
const HI=['bg-indigo-500/15','text-white'];
function run(){{const n=Math.max(0,+N.value||0),k=yearly?'annual_per_month':'monthly',
f=P.filter(p=>p.credits>=n).sort((a,b)=>a[k]-b[k])[0];
document.querySelectorAll('article[data-plan]').forEach(c=>{{const on=!!f&&c.dataset.plan===f.name;['outline-2','outline-emerald-400','outline-offset-4'].forEach(x=>c.classList.toggle(x,on));}});
document.querySelectorAll('tr[data-tier]').forEach(r=>{{const on=!!f&&r.dataset.tier===f.name;HI.forEach(x=>r.classList.toggle(x,on));r.toggleAttribute('data-picked',on);}});
document.querySelectorAll('[data-annual]').forEach(s=>s.textContent=C+s.dataset[yearly?'annual':'monthly']);
document.querySelectorAll('[data-note]').forEach(s=>s.textContent=s.dataset[yearly?'annualNote':'monthlyNote']);
document.getElementById('price').textContent=f?C+f[k].toLocaleString('en-US')+'/mo':'Custom';
document.getElementById('plan').textContent=f?(f.label+', '+C+(f[k]*12).toLocaleString('en-US')+' a year'+(yearly?' paid up front.':' if you stay 12 months.')):'Above the largest plan. Ask {tool} sales for a quote.';}}
R.oninput=()=>{{N.value=R.value;run();}};N.oninput=()=>{{R.value=Math.min(+N.value||0,{top});run();}};
function bill(y){{yearly=y;Y.setAttribute('aria-pressed',y);M.setAttribute('aria-pressed',!y);run();}}
if(Y){{Y.onclick=()=>bill(true);M.onclick=()=>bill(false);}}run();
</script>"""
    title = f"{d['tool']} Pricing {d['checked'][:4]}: Plans, {d.get('unit_label', 'Credits')} & Cost Calculator"
    free = "Free, then " if any(p.get("monthly") == 0 for p in plans) else ""
    desc = (f"{d['tool']} pricing checked {checked}: {free}{cur}{lo['monthly']}-{cur}{hi['monthly']}/mo "
            f"(or {cur}{lo['annual_per_month']}-{cur}{hi['annual_per_month']}/mo yearly). {d.get('unit_label', 'Credits')} per plan and a calculator.")
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
    n = len(d["plans"])
    widths = ("*:w-full sm:*:w-[calc(50%-0.625rem)] lg:*:w-[calc(25%-0.9375rem)]" if n >= 4
              else "*:w-full md:*:w-[calc(50%-0.625rem)]")
    cards = "".join(plan_card(p, link_of(d)) for p in d["plans"])
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

<section aria-labelledby="plans-h" class="mt-16">
 <h2 id="plans-h" class="{H2}">{tool} plans</h2>
 <div class="mx-auto mt-10 flex {"max-w-4xl" if n < 4 else ""} flex-wrap justify-center gap-5 {widths}">{cards}</div>
 <p class="mx-auto mt-6 max-w-3xl text-center text-sm text-slate-500">{e(d["after_plans"])}</p>
 <div class="text-center">{compare_btn(d)}</div>
</section>

<section aria-labelledby="comp-h" class="mx-auto mt-16 max-w-4xl">
 <div class="{PANEL} p-6 sm:p-8">
  <h2 id="comp-h" class="text-xl font-semibold text-balance text-white">{e(d["components_title"])}</h2>
  <table class="mt-4 {TABLE}"><tbody>{comps}</tbody></table>
  <p class="mt-6 border-t border-slate-800 pt-6 text-xs text-slate-500">{e(d["calc_note"])}</p>
 </div>
</section>
{faq_html}
{page_end([d], cta=False)}

<script>
const C={calc},R=document.getElementById('range'),N=document.getElementById('need');
let fee=C.fee;
const $=v=>'$'+Math.round(v).toLocaleString('en-US');
function run(){{const n=Math.max(0,+N.value||0),a=$(n*C.lo+fee),b=$(n*C.hi+fee);
document.getElementById('price').textContent=(a===b?a:a+' to '+b)+'/mo';
document.getElementById('typ').textContent=C.typ===null?'':C.typLabel+': '+$(n*C.typ+fee)+'/mo';
document.getElementById('plan').textContent=n.toLocaleString('en-US')+' minutes at about $'+C.lo.toFixed(2)+' to $'+C.hi.toFixed(2)+' a minute'+(fee?', plus $'+fee+' a month.':'.');}}
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
    lede = f'{e(a["tool"])} and {e(b["tool"])} pricing side by side.'
    ca, cb = a.get("currency", "$"), b.get("currency", "$")
    if ca != cb:  # never convert: each vendor's own currency, said plainly
        names_of = {"$": "US dollars ($)", "€": "euros (€)"}
        lede += (f' {e(a["tool"])} lists prices in {names_of.get(ca, ca)} and {e(b["tool"])} in {names_of.get(cb, cb)}.'
                 ' We show each as published and do not convert them.')
    body = hero(checked, f"{names} pricing", "text-4xl sm:text-5xl lg:text-6xl", lede) + f"""

<section aria-labelledby="cmp-h" class="mx-auto max-w-4xl {PANEL} p-6 sm:p-8">
 <h2 id="cmp-h" class="text-xl font-semibold text-white">Side by side</h2>
 <table class="mt-4 {TABLE}">
  <thead class="text-xs text-slate-500 max-sm:sr-only"><tr><th scope="col" class="py-2 pr-4 font-normal">&nbsp;</th><th scope="col" class="py-2 pr-4 font-normal">{e(a['tool'])}</th><th scope="col" class="py-2 pr-4 font-normal">{e(b['tool'])}</th></tr></thead>
  <tbody>{rows}</tbody>
 </table>
</section>

<section class="mx-auto mt-10 grid max-w-4xl gap-5 md:grid-cols-2">{cards}</section>
{page_end([a, b], cta=False)}"""
    title = f"{names} Pricing {max(a['checked'], b['checked'])[:4]}: Plans and Costs Side by Side"
    desc = f"{names} pricing side by side, copied from each official pricing page. Checked {checked}."
    return page(title, desc, f"/{c['slug']}/", body)


CATEGORIES = [
    ("app-builders", "AI app builders", "Build apps by describing them. Compare plans, credits and what a month of building really costs.",
     ["base44", "lovable"], "base44-vs-lovable"),
    ("voice-agents", "AI voice agents", "Phone agents billed by the minute. See the per-minute rate and your bill for your call volume.",
     ["retell", "vapi"], "vapi-vs-retell-ai"),
    ("automation", "Automation", "Workflow automation billed by runs or credits. See what your monthly volume costs, in each vendor's own currency.",
     ["n8n", "make"], "n8n-vs-make"),
]
HOME_TOOLS = ("base44", "lovable", "retell", "vapi", "n8n", "make")


def home_page(tools):
    latest = fmt_date(max(d["checked"] for d in tools.values()))
    jump = "".join(f'<a href="/{tools[k]["slug"]}/" class="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-2 text-center text-sm font-medium whitespace-nowrap text-slate-200 sm:px-4 '
                   f'hover:border-indigo-400/60 hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-400">{e(tools[k]["tool"])} pricing</a>'
                   for k in HOME_TOOLS)
    cards = ""
    for cid, title, blurb, keys, vs in CATEGORIES:
        rows = "".join(f'<li><a href="/{tools[k]["slug"]}/" class="flex justify-between gap-3 rounded-lg px-3 py-2 text-slate-200 hover:bg-slate-800/60 hover:text-white">'
                       f'{e(tools[k]["tool"])} pricing<span class="text-slate-500">{e(start_price(tools[k]))}</span></a></li>' for k in keys)
        a, b = tools[keys[0]]["tool"], tools[keys[1]]["tool"]
        cards += f"""<article id="{cid}" class="scroll-mt-16 {PANEL} flex flex-col p-6 transition-colors hover:border-indigo-500/50">
 <h3 class="text-lg font-semibold text-white">{e(title)}</h3>
 <p class="mt-2 text-sm text-slate-400">{e(blurb)}</p>
 <ul class="mt-5 flex-1 space-y-1 text-sm">{rows}</ul>
 <a href="/{vs}/" class="mt-4 {LINK} text-sm">Compare {e(a)} and {e(b)}</a>
</article>"""
    widget = {k: widget_data(tools[k]) for k in HOME_TOOLS}
    tabs = "".join(f'<button type="button" data-tool="{k}" aria-pressed="{str(i == 0).lower()}" class="{SEG}">{e(tools[k]["tool"])}</button>'
                   for i, k in enumerate(widget))
    body = f"""
<section class="pt-12 pb-10 text-center sm:pt-20">
 <p class="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/70 px-3.5 py-1 text-xs text-slate-300 backdrop-blur-md">
  <span class="relative flex h-2 w-2"><span class="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 motion-safe:animate-ping"></span><span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-400"></span></span>
  Prices checked {latest}</p>
 <h1 class="mx-auto mt-6 {H1} text-3xl min-[400px]:text-4xl sm:text-5xl lg:text-6xl">Transparent pricing for AI builders</h1>
 <p class="mx-auto mt-5 max-w-2xl text-lg text-pretty text-slate-400">Independent, dated prices for AI app builders, voice agents and automation tools. See what you would really pay before you pick a tool.</p>
 <div class="mx-auto mt-8 grid max-w-md grid-cols-2 gap-3 sm:max-w-none sm:w-fit sm:grid-cols-3">{jump}</div>
</section>

<section id="calculator" aria-labelledby="calc-h" class="mx-auto max-w-4xl scroll-mt-16 {PANEL} p-6 shadow-[0_0_60px_-20px_rgba(99,102,241,0.45)] sm:p-8">
 <h2 id="calc-h" class="text-xl font-semibold text-white">Quick cost calculator</h2>
 <div role="group" aria-label="Tool" class="mt-5 grid grid-cols-2 gap-1 rounded-lg border border-slate-700 bg-slate-950/60 p-1 text-sm sm:grid-cols-3">{tabs}</div>
 <div class="mt-8 grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
  <div>
   <div class="flex items-baseline justify-between gap-3">
    <label for="w-range" id="w-label" class="text-sm text-slate-400"></label>
    <input id="w-need" type="number" min="0" inputmode="numeric" aria-labelledby="w-label" class="w-28 {NUM}">
   </div>
   <input id="w-range" type="range" min="0" class="mt-4 w-full accent-indigo-500">
  </div>
  <div aria-live="polite" class="md:min-w-64 md:text-right">
   <p class="text-sm text-slate-400">Estimated monthly cost</p>
   <p id="w-price" class="mt-1 text-4xl font-semibold tracking-tight text-white tabular-nums sm:text-5xl"></p>
   <p id="w-plan" class="mt-2 text-sm text-slate-400"></p>
  </div>
 </div>
 <p class="mt-6 text-xs text-slate-500"><span id="w-note"></span> Each tool counts usage its own way, so a credit on one is not a credit on another. <a id="w-link" class="{LINK}" href="#">See the full breakdown</a>.</p>
</section>

<section aria-labelledby="cat-h" class="mt-16">
 <h2 id="cat-h" class="{H2}">Pick a category</h2>
 <div class="mt-10 grid gap-5 lg:grid-cols-3">{cards}</div>
</section>

<section class="mx-auto mt-16 max-w-3xl {PANEL} p-6 text-sm text-slate-400">
 <p><span class="font-medium text-slate-200">How we get these numbers.</span> Every price on this site is copied from the vendor's official pricing page, with the date we checked it. A script reads those pages every day and flags any change, and a person updates the numbers after checking. We are not paid by any company listed. <a class="{LINK}" href="/about/">More about this site</a>.</p>
</section>
<script>
const W={json.dumps(widget)},T=document.querySelectorAll('[data-tool]'),R=document.getElementById('w-range'),N=document.getElementById('w-need'),$=id=>document.getElementById(id);
let cur='base44';
const fmt=n=>W[cur].cur+Math.round(n).toLocaleString('en-US');
function run(){{const w=W[cur],n=Math.max(0,+N.value||0);
 if(w.kind==='usage'){{const lo=n*w.low,hi=n*w.high;$('w-price').textContent=fmt(lo)+(Math.round(hi)>Math.round(lo)?' to '+fmt(hi):'');
  $('w-plan').textContent=w.typical?(w.typical_label+': '+fmt(n*w.typical)+' a month.'):'Pay as you go, no monthly package.';}}
 else{{const f=w.options.filter(o=>o.credits>=n).sort((a,b)=>a.monthly-b.monthly)[0];
  $('w-price').textContent=f?fmt(f.monthly):'Custom';$('w-plan').textContent=f?(f.label+', billed monthly.'):'Above the largest public plan.';}}}}
function pick(k){{cur=k;const w=W[k];T.forEach(t=>t.setAttribute('aria-pressed',t.dataset.tool===k));
 $('w-label').textContent=w.label;R.max=w.max;R.step=w.step;N.value=R.value=w.start;$('w-note').textContent=w.note;$('w-link').href=w.href;run();}}
T.forEach(t=>t.onclick=()=>pick(t.dataset.tool));R.oninput=()=>{{N.value=R.value;run();}};N.oninput=()=>{{R.value=Math.min(+N.value||0,+R.max);run();}};pick(cur);
</script>"""
    return page("AI Stack Prices: The Cost and Pricing Hub for AI Builders",
                "Independent, dated pricing for AI app builders, voice agents and automation tools, with cost calculators. Copied from official pricing pages and checked daily.",
                "/", body)


def start_price(d):
    if d["kind"] == "usage":
        return f"from ${d['per_min_low']:.2f}/min"
    return f"from {d.get('currency', '$')}{min(p['monthly'] for p in calc_options(d) if p['monthly'])}/mo"


def widget_data(d):
    base = {"href": f"/{d['slug']}/", "cur": d.get("currency", "$")}
    if d["kind"] == "usage":
        return {**base, "kind": "usage", "label": "Call minutes per month", "max": 20000, "step": 100, "start": 1000,
                "low": d["per_min_low"], "high": d["per_min_high"], "typical": d.get("per_min_typical"),
                "typical_label": d.get("typical_label", ""), "note": f"Range from {d['tool']}'s published per-minute prices."}
    opts = calc_options(d)
    return {**base, "kind": "credits", "label": d["calc_label"], "max": max(o["credits"] for o in opts),
            "step": 5 if max(o["credits"] for o in opts) <= 2000 else 50, "start": 150,
            "options": [{"label": o["name"] if "tiers" in d else o["name"] + " plan", "credits": o["credits"], "monthly": o["monthly"]} for o in opts],
            "note": f"Cheapest {d['tool']} plan that covers this, on monthly billing."}


def about_page(tools):
    rows = "".join(f'<li><a class="{LINK}" href="{e(d["source_url"])}">{e(d["tool"])}</a>, checked {fmt_date(d["checked"])}</li>' for d in tools.values())
    body = f"""
<section class="mx-auto max-w-3xl pt-12 sm:pt-20">
 <h1 class="{H1} text-4xl sm:text-5xl">About AI Stack Prices</h1>
 <div class="mt-8 space-y-5 text-lg leading-relaxed text-slate-300">
  <p>AI Stack Prices shows what AI app builders, voice-agent platforms and automation tools really cost, so you can compare them before you sign up.</p>
  <p>Every price is copied by hand from the vendor's official pricing page, with the date we checked it. Our calculators only use those published numbers. Where a vendor publishes a range or leaves something out, we say so instead of guessing.</p>
  <p>A script reads each official pricing page every day and flags any change. A person checks the change and then updates this site.</p>
  <p>We are independent and not affiliated with any company listed. If we join a company's affiliate program, links to it will say so next to the link. That never changes the prices we show.</p>
 </div>
 <h2 class="mt-12 text-xl font-semibold text-white">Sources</h2>
 <ul class="mt-4 space-y-2 text-slate-400">{rows}</ul>
</section>"""
    return page("About AI Stack Prices", "How AI Stack Prices collects, dates and checks the AI tool prices it publishes.", "/about/", body)


WEB3FORMS_KEY = "7736e9fb-e54c-4060-8401-e783c4ea923e"  # Web3Forms access key; while empty the contact form renders disabled with a mailto fallback
MAIL = "hello@aistackprices.com"
FIELD = ("mt-2 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-white placeholder:text-slate-500 "
         "focus:border-indigo-400 focus:outline-2 focus:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-60")


def contact_page():
    live = bool(WEB3FORMS_KEY)
    mail = f'<a class="{LINK}" href="mailto:{MAIL}">{MAIL}</a>'
    off = "" if live else (f'<p class="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">'
                           f'The form is not switched on yet. Please email us at {mail} instead.</p>')
    script = "" if not live else f"""
<script>
const F=document.getElementById('contact-form'),S=document.getElementById('form-status');
F.onsubmit=async ev=>{{ev.preventDefault();const b=F.querySelector('button[type=submit]');b.disabled=true;S.className='mt-4 text-sm text-slate-400';S.textContent='Sending...';
 try{{const r=await fetch(F.action,{{method:'POST',headers:{{'Content-Type':'application/json',Accept:'application/json'}},body:JSON.stringify(Object.fromEntries(new FormData(F)))}});
  const j=await r.json();if(!r.ok||!j.success)throw 0;F.reset();S.className='mt-4 text-sm text-emerald-300';S.textContent='Thanks, your message was sent. We usually reply within a few days.';}}
 catch(_){{S.className='mt-4 text-sm text-rose-300';S.innerHTML='Sorry, your message could not be sent. Please email us at <a class="underline" href="mailto:{MAIL}">{MAIL}</a>.';}}
 b.disabled=false;}};
</script>"""
    body = f"""
<section class="mx-auto max-w-xl pt-12 sm:pt-20">
 <h1 class="{H1} text-4xl sm:text-5xl">Contact</h1>
 <p class="mt-6 text-lg leading-relaxed text-slate-300">Send us questions, price corrections or partnership requests. If a price looks wrong, include the link to our page and we will fix it after checking the official pricing page.</p>
 <div class="mt-8 {PANEL} p-6 sm:p-8">{off}
  <form id="contact-form" action="https://api.web3forms.com/submit" method="POST">
   <fieldset{"" if live else " disabled"} class="space-y-5">
    <legend class="sr-only">Send a message</legend>
    <input type="hidden" name="access_key" value="{e(WEB3FORMS_KEY)}">
    <input type="hidden" name="subject" value="New message from aistackprices.com">
    <input type="checkbox" name="botcheck" class="hidden" tabindex="-1" autocomplete="off">
    <div><label for="c-name" class="text-sm font-medium text-slate-200">Name</label>
     <input id="c-name" name="name" type="text" required autocomplete="name" class="{FIELD}"></div>
    <div><label for="c-email" class="text-sm font-medium text-slate-200">Email</label>
     <input id="c-email" name="email" type="email" required autocomplete="email" class="{FIELD}"></div>
    <div><label for="c-message" class="text-sm font-medium text-slate-200">Message</label>
     <textarea id="c-message" name="message" rows="6" required class="{FIELD}"></textarea></div>
    <button type="submit" class="{CTA} w-full disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto">Send message</button>
   </fieldset>
  </form>
  <p id="form-status" role="status" aria-live="polite" class="mt-4 text-sm"></p>
 </div>
 <p class="mt-6 text-sm text-slate-400">You can also email us at {mail}.</p>
</section>{script}"""
    return page("Contact AI Stack Prices", "Questions, price corrections or partnership requests for AI Stack Prices.", "/contact/", body)


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
    a_cls = "hover:text-white focus-visible:outline-2 focus-visible:outline-indigo-400 rounded"
    CHROME.update(
        nav="".join(f'<a class="{a_cls}" href="{h}">{t}</a>' for t, h in
                    [("App Builders", "/#app-builders"), ("Voice Agents", "/#voice-agents"), ("Automation", "/#automation"), ("Cost Calculators", "/#calculator"), ("About", "/about/"), ("Contact", "/contact/")]),
        css_v=hashlib.sha256((ROOT / "static" / "site.css").read_bytes()).hexdigest()[:10])
    pairs = json.loads((ROOT / "data" / "compare.json").read_text())
    for c in pairs:  # each tool page links to its comparison page
        tools[c["a"]]["compare_with"] = (c["slug"], tools[c["b"]]["tool"])
        tools[c["b"]]["compare_with"] = (c["slug"], tools[c["a"]]["tool"])
    for d in tools.values():
        out[f"/{d['slug']}/"] = ((credits_page if d["kind"] == "credits" else usage_page)(d), d["checked"])
    comps = []
    for c in pairs:
        a, b = tools[c["a"]], tools[c["b"]]
        comps.append((c, a, b))
        out[f"/{c['slug']}/"] = (compare_page(c, a, b), max(a["checked"], b["checked"]))
    out["/"] = (home_page(tools), max(d["checked"] for d in tools.values()))
    out["/about/"] = (about_page(tools), max(d["checked"] for d in tools.values()))
    out["/contact/"] = (contact_page(), max(d["checked"] for d in tools.values()))
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
