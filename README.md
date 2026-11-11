# AI Stack Prices

Build: `python3 build.py` (outputs `dist/`). After changing Tailwind classes in `build.py`, run `npm install && npm run css` and commit `static/site.css`.

Check: `python3 tests/check_layout.py` (12 screen widths).

Price check: `python3 scripts/check_prices.py` (runs daily in GitHub Actions; opens an issue when a pricing page changes, never edits data/).
