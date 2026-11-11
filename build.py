"""Builds the static site into dist/. Prices come only from data/*.json, never from an LLM.

Styling: Tailwind classes in this file are compiled once into static/site.css (see README),
so visitors download a small CSS file instead of the Tailwind runtime.
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
    assert sum(p.get("popular", False) for p in plans) <= 1


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


def plan_card(p, link):
    pop = p.get("popular", False)
    ring = ("bg-gradient-to-b from-indigo-500 via-violet-500 to-indigo-500/20 shadow-[0_0_40px_-8px_rgba(139,92,246,0.55)]"
            if pop else "bg-slate-800")
    badge = ('<span class="whitespace-nowrap rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-medium text-indigo-300">'
             'Most popular</span>') if pop else ""
    if p["monthly"]:
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
    btn = ("bg-gradient-to-r from-indigo-500 to-violet-500 text-white hover:from-indigo-400 hover:to-violet-400"
           if pop else "border border-slate-700 text-slate-200 hover:border-slate-500 hover:text-white")
    return f"""<article data-plan="{e(p['name'])}" class="rounded-2xl p-px {ring}">
 <div class="flex h-full flex-col rounded-[15px] bg-slate-900/80 p-6 backdrop-blur-md">
  <div class="flex items-center justify-between gap-2"><h3 class="text-lg font-semibold text-white">{e(p['name'])}</h3>{badge}</div>
  {price}
  <dl class="mt-5 space-y-1 border-y border-slate-800 py-4 text-sm">
   <div class="flex justify-between gap-3"><dt class="text-slate-400">Message credits</dt><dd class="font-medium text-white tabular-nums">{p['message_credits']:,}/mo</dd></div>
   <div class="flex justify-between gap-3"><dt class="text-slate-400">Integration credits</dt><dd class="font-medium text-white tabular-nums">{p['integration_credits']:,}/mo</dd></div>
  </dl>
  <ul class="mt-4 flex-1 space-y-2 text-sm text-slate-300">{feats}</ul>
  <a href="{e(link)}" rel="nofollow sponsored" class="mt-6 block rounded-lg px-4 py-2.5 text-center text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 {btn}">Choose {e(p['name'])}</a>
 </div>
</article>"""


def pricing_page(d):
    plans = d["plans"]
    tool = e(d["tool"])
    link = d["affiliate_url"] or d["source_url"]
    checked = fmt_date(d["checked"])
    top = max(p["message_credits"] for p in plans)
    paid = [p for p in plans if p["monthly"]]
    lo, hi = paid[0], paid[-1]
    disclosure = ("Some links on this page are affiliate links: if you buy through them we may earn a commission, "
                  "at no extra cost to you. It never changes the prices shown." if d["affiliate_url"] else
                  "We don't earn anything from the links on this page.")
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
         "actions. Message credits and integration credits are counted separately, and usage per action "
         "varies with the AI model you select."),
    ]
    faq_html = "".join(f"""<details class="group rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 backdrop-blur-md">
<summary class="flex cursor-pointer list-none justify-between gap-4 rounded font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-400">{e(q)}<span aria-hidden="true" class="text-slate-500 transition-transform group-open:rotate-45">+</span></summary>
<p class="mt-3 text-sm leading-relaxed text-slate-400">{e(a)}</p></details>""" for q, a in faq)
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    calc_data = json.dumps([{k: p[k] for k in ("name", "monthly", "annual_per_month", "message_credits")}
                            for p in plans])
    cards = "".join(plan_card(p, link) for p in plans)
    body = f"""
<section class="pt-16 pb-10 text-center sm:pt-24">
 <p class="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/70 px-3.5 py-1 text-xs text-slate-300 backdrop-blur-md">
  <span class="relative flex h-2 w-2"><span class="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 motion-safe:animate-ping"></span><span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-400"></span></span>
  Prices checked {checked}</p>
 <h1 class="mx-auto mt-6 bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-4xl font-semibold tracking-tight text-balance text-transparent sm:text-6xl">{tool} pricing and real costs</h1>
 <p class="mx-auto mt-5 max-w-2xl text-lg text-pretty text-slate-400">Every {tool} plan, how many credits it gives you, and the cheapest one for how much you build. Copied from the <a class="text-indigo-300 underline decoration-indigo-500/40 underline-offset-4 hover:text-white" href="{e(d['source_url'])}">official pricing page</a>.</p>
</section>

<section aria-labelledby="calc-h" class="mx-auto max-w-4xl rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-[0_0_60px_-20px_rgba(99,102,241,0.45)] backdrop-blur-md sm:p-8">
 <div class="flex flex-wrap items-center justify-between gap-4">
  <h2 id="calc-h" class="text-xl font-semibold text-white">Cost calculator</h2>
  <div role="group" aria-label="Billing period" class="inline-flex rounded-lg border border-slate-700 bg-slate-950/60 p-1 text-sm">
   <button type="button" id="yr" aria-pressed="true" class="rounded-md px-3 py-1.5 whitespace-nowrap text-slate-400 focus-visible:outline-2 focus-visible:outline-indigo-400 aria-pressed:bg-indigo-500 aria-pressed:text-white">Yearly, save 20%</button>
   <button type="button" id="mo" aria-pressed="false" class="rounded-md px-3 py-1.5 whitespace-nowrap text-slate-400 focus-visible:outline-2 focus-visible:outline-indigo-400 aria-pressed:bg-indigo-500 aria-pressed:text-white">Monthly</button>
  </div>
 </div>
 <div class="mt-8 grid gap-8 md:grid-cols-[1fr_auto] md:items-end">
  <div>
   <div class="flex items-baseline justify-between gap-3">
    <label for="range" class="text-sm text-slate-400">AI message credits you use each month</label>
    <input id="need" type="number" min="0" inputmode="numeric" value="150" aria-label="Message credits per month" class="w-24 rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-right font-medium text-white tabular-nums focus-visible:outline-2 focus-visible:outline-indigo-400">
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
 <p class="mt-6 text-xs text-slate-500">{tool} says credit use varies by action and AI model, so treat this as an estimate.</p>
</section>

<section aria-labelledby="plans-h" class="mt-24">
 <h2 id="plans-h" class="text-center text-3xl font-semibold tracking-tight text-balance text-white">All {tool} plans</h2>
 <p class="mt-3 text-center text-slate-400">The plan that fits your usage gets a green outline as you move the calculator.</p>
 <div class="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">{cards}</div>
 <p class="mt-6 text-center text-sm text-slate-500">Enterprise pricing is custom, by quote from {tool} sales.</p>
</section>

<section aria-labelledby="faq-h" class="mx-auto mt-24 max-w-3xl">
 <h2 id="faq-h" class="text-center text-3xl font-semibold tracking-tight text-balance text-white">Questions people ask</h2>
 <div class="mt-8 space-y-3">{faq_html}</div>
</section>

<section class="mx-auto mt-16 max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-400 backdrop-blur-md">
 <p><span class="font-medium text-slate-200">How we get these numbers.</span> We copy each price from {tool}'s official pricing page and note the date we checked it: {checked}. {disclosure}</p>
 <a href="{e(link)}" rel="nofollow sponsored" class="mt-5 inline-block rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-5 py-2.5 font-medium text-white hover:from-indigo-400 hover:to-violet-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400">See {tool}'s current plans</a>
</section>

<script>
const P={calc_data},R=document.getElementById('range'),N=document.getElementById('need'),Y=document.getElementById('yr'),M=document.getElementById('mo');
let yearly=true;
function run(){{const n=Math.max(0,+N.value||0),k=yearly?'annual_per_month':'monthly',
f=P.filter(p=>p.message_credits>=n).sort((a,b)=>a[k]-b[k])[0];
document.querySelectorAll('article[data-plan]').forEach(c=>{{const on=!!f&&c.dataset.plan===f.name;['outline-2','outline-emerald-400','outline-offset-4'].forEach(x=>c.classList.toggle(x,on));}});
document.querySelectorAll('[data-annual]').forEach(s=>s.textContent='$'+s.dataset[yearly?'annual':'monthly']);
document.querySelectorAll('[data-note]').forEach(s=>s.textContent=s.dataset[yearly?'annualNote':'monthlyNote']);
document.getElementById('price').textContent=f?'$'+f[k]+'/mo':'Custom';
document.getElementById('plan').textContent=f?(f.name+' plan, $'+(f[k]*12).toLocaleString('en-US')+' a year'+(yearly?' paid up front.':' if you stay 12 months.')):'Above the largest plan. Ask {tool} sales for a quote.';}}
R.oninput=()=>{{N.value=R.value;run();}};N.oninput=()=>{{R.value=Math.min(+N.value||0,{top});run();}};
function bill(y){{yearly=y;Y.setAttribute('aria-pressed',y);M.setAttribute('aria-pressed',!y);run();}}
Y.onclick=()=>bill(true);M.onclick=()=>bill(false);run();
</script>"""
    title = f"{d['tool']} Pricing {d['checked'][:4]}: Plans, Credits & Cost Calculator"
    desc = (f"{d['tool']} pricing checked {checked}: Free, then ${lo['monthly']}-${hi['monthly']}/mo "
            f"(or ${lo['annual_per_month']}-${hi['annual_per_month']}/mo yearly). Credits per plan and a calculator.")
    return page(title, desc, f"/{d['slug']}/", body, schema)


def main():
    pages = []
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST)
    for f in sorted((ROOT / "data").glob("*.json")):
        d = json.loads(f.read_text())
        self_check(d)
        out = DIST / d["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pricing_page(d))
        pages.append(d)
    links = "".join(f'<li><a class="flex flex-wrap justify-between gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-4 font-medium text-white hover:border-indigo-500/60" href="/{d["slug"]}/">{e(d["tool"])} pricing<span class="text-sm text-slate-500">checked {fmt_date(d["checked"])}</span></a></li>' for d in pages)
    (DIST / "index.html").write_text(page(
        "AI Stack Prices: Real Costs of AI App Builders and Voice Agents",
        "Sourced, dated pricing for AI app builders and voice-agent platforms, with cost calculators.", "/",
        f'<section class="mx-auto max-w-3xl pt-16 sm:pt-24"><h1 class="bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-4xl font-semibold tracking-tight text-balance text-transparent sm:text-6xl">What AI tools cost</h1>'
        f'<p class="mt-5 text-lg text-slate-400">Plans, credits and calculators for AI app builders and voice agents, copied from each official pricing page with the date we checked.</p>'
        f'<ul class="mt-10 space-y-3">{links}</ul></section>'))
    print(f"built {len(pages)} pricing page(s) into {DIST}")


if __name__ == "__main__":
    main()
