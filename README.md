# Price Drop and Back-in-Stock Email Alerts with Python and GitHub Actions

A free price tracker that runs on GitHub Actions: list the products you care about in a YAML file and get one email when the price drops or the item is back in stock. Written in Python 3.12, it reads schema.org product data, remembers what it already told you, and sends alerts through the Mailtrap Email API.

- **No server, no database.** A scheduled GitHub Actions workflow does the checking, and the state is two small files committed back to the repo.
- **One secret.** Only `MAILTRAP_API_TOKEN`; everything else is in `watchlist.yaml`.
- **No duplicate emails.** Each alert fires once when its condition becomes true, then stays quiet until it resets.

## Before you start

You need:

1. **A Mailtrap account.** Sign up at [mailtrap.io](https://mailtrap.io). The free plan is enough for personal alerts.
2. **A verified sending domain.** In Mailtrap, go to **Sending Domains**, add a domain you own and add the DNS records it shows. Your `from_email` must be on this domain. Mailtrap won't send from `@gmail.com` or similar addresses.
3. **An API token for the Transactional stream.** Go to **Sending Domains → your domain → Integration**, choose the **Transactional** stream and **API**, and copy the token. (Don't use the Sandbox or Bulk stream.)

## Quick start

1. **Create your copy.** Click **Use this template** (or fork) on GitHub.
2. **Add the secret.** In your repo, go to **Settings → Secrets and variables → Actions → New repository secret**. Set the name to `MAILTRAP_API_TOKEN` and the value to your token.
3. **Edit `watchlist.yaml`.** Set `settings.from_email` to an address on your verified domain, set `default_recipients` to your inbox, and replace the example item with your products.
4. **Run the workflow.** Open the **Actions** tab and enable workflows if GitHub asks. Then choose **Price alerts → Run workflow**.
5. **Get your first alert.** The first run only records baselines (current prices and stock), so it usually sends nothing. To test right away, set an item's `target_price` above its current price with `notify_on: [price_below]`, run the workflow again, and you'll get a "Price alert" email.

After that the workflow runs every 6 hours (`17 */6 * * *`) and commits price changes to `data/`.

## `watchlist.yaml` reference

```yaml
settings:
  from_email: alerts@yourdomain.com   # must be on a Mailtrap-verified sending domain
  from_name: Price Alerts
  default_recipients: [you@example.com]
  request_delay_seconds: 5            # delay between requests to the same host
  timeout_seconds: 20
  respect_robots_txt: true
  digest: false                       # DIGEST env var overrides
items:
  - name: Example Headphones
    url: https://example.com/product/123
    selector: ".price"                # optional CSS fallback for price
    stock_selector: ".availability"   # optional
    out_of_stock_text: ["out of stock", "sold out"]  # optional
    target_price: 199.99              # needed for price_below
    drop_percent: 10                  # needed for drop_percent
    notify_on: [price_below, drop_percent, back_in_stock]
    recipients: [you@example.com]     # optional, falls back to default_recipients
```

| Field | Required | Meaning |
|---|---|---|
| `settings.from_email` | yes | Sender address. Its domain must be verified in Mailtrap. |
| `settings.from_name` | no | Sender name. Default: `Price Alerts`. |
| `settings.default_recipients` | yes, unless every item has `recipients` | Where alerts and the digest go. |
| `settings.request_delay_seconds` | no | Minimum time between two requests to the same host. Default: 5. |
| `settings.timeout_seconds` | no | HTTP timeout per request. Default: 20. |
| `settings.respect_robots_txt` | no | Skip URLs that `robots.txt` disallows, and report them as failures. Default: `true`. |
| `settings.digest` | no | Send a daily summary. Default: `false`. The `DIGEST` variable overrides it. |
| `items[].name` | yes | Must be unique. Its slug (`example-headphones`) is the item's key in `data/state.json`, so if you rename an item, its history starts over. |
| `items[].url` | yes | An `http(s)` product page. |
| `items[].selector` | no | CSS selector for the price, used only when the page has no schema.org price. |
| `items[].stock_selector` | no | CSS selector for the element with the stock text. |
| `items[].out_of_stock_text` | no | If the stock element contains any of these strings (case-insensitive), the item counts as out of stock. Default: `["out of stock", "sold out"]`. |
| `items[].target_price` | for `price_below` | Get an alert when the price is at or below this value. |
| `items[].drop_percent` | for `drop_percent` | Get an alert when the price falls at least this many percent below the baseline. |
| `items[].notify_on` | no | Any of `price_below`, `drop_percent`, `back_in_stock`. Default: every rule the item has numbers for, plus `back_in_stock`. |
| `items[].recipients` | no | Overrides `default_recipients` for this item. |

The watchlist is validated before anything is fetched. Errors name the item and the field, for example:

```
watchlist.yaml is invalid:
  - item 'Example Headphones': target_price: required when notify_on includes price_below
```

## How alerts and dedup work

Each check either succeeds (a price and/or stock status was found) or fails. Every rule alerts **once, when its condition becomes true**, and stays quiet until the condition resets:

| Rule | Fires when | Resets when |
|---|---|---|
| `price_below` | price ≤ `target_price` | price goes back above `target_price` |
| `drop_percent` | price ≤ baseline × (1 − `drop_percent`/100). The baseline is the first price seen, never alerted on. After an alert, the baseline moves to the new price. | The baseline also moves up whenever the price rises above it. |
| `back_in_stock` | stock changes from out of stock to in stock (not on the first check, and not from "unknown") | the item goes out of stock again |
| watcher error | 3 failed checks in a row. You get one email with the URL, the last error and a hint. | the next successful check |

Every alert is a separate email. Each email type has a Mailtrap category, so you can filter them in Mailtrap's stats:

| Email | Category |
|---|---|
| `price_below`, `drop_percent` | `price-alert` |
| `back_in_stock` | `stock-alert` |
| 3 failures in a row | `watcher-error` |
| Daily digest | `digest` |

**If a send fails** (bad token, unverified domain, outage), the alert is **not** marked as sent, so it's retried on the next run. Other items are still processed, and the run exits with code 2 so the workflow shows red.

**Where prices come from:** the tool reads schema.org `Product` JSON-LD first, which most shops include for Google. It handles `@graph`, top-level lists, `@type` lists, `Offer`, offer lists and `AggregateOffer` (`lowPrice`), and every `availability` spelling. If there's no usable JSON-LD, it uses your CSS `selector`. `PreOrder` and `BackOrder` count as *not in stock*, so the back-in-stock email means you can actually buy the item now.

## Daily digest

Set `digest: true` in `watchlist.yaml`, or set a repository **variable** (not a secret) `DIGEST=true` under **Settings → Secrets and variables → Actions → Variables**. You'll get at most one email per UTC day. It lists every item's current price, change over the last 24 hours, stock and status (for example `failing (3x): HTTP 503`).

## Dry run

A dry run fetches and evaluates everything and saves each email that *would* be sent to `out/<timestamp>_<item>_<kind>.html`. It sends nothing and leaves `data/` unchanged.

```bash
python -m price_alerts --dry-run
```

On GitHub, choose **Run workflow** and tick **dry_run**. The previews are uploaded as the `email-previews` artifact on the run page. You can also set `DRY_RUN=true` as an environment variable.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt      # runtime deps + pytest, and installs this package

cp .env.example .env                     # then paste your token into .env
python -m price_alerts --dry-run -v      # see what would happen
python -m price_alerts                   # real run: sends email, updates data/
```

```
python -m price_alerts [--watchlist watchlist.yaml] [--data-dir data] [--dry-run] [--only NAME] [-v]
```

- `--only NAME` checks a single item, by name or id. This is handy when you're testing a selector.
- `-v` turns on debug logging.
- Exit codes: `0` OK (failed product checks don't change it), `1` config error, `2` at least one email failed to send.

The tool reads `.env` only if the file exists, never overrides variables already set in your shell, and never prints the token. `.env` is git-ignored.

## Finding a CSS selector

You only need a selector when the page has no schema.org price. To check, view the page source and search for `application/ld+json` and `"Product"`, or run `python -m price_alerts --dry-run --only "Item name" -v`. The log says `via json-ld` or `via selector`.

1. Open the product page, right-click the price and choose **Inspect**.
2. Find a stable class or attribute on the element, such as `.price`, `.product-price .amount` or `[itemprop="price"]`. Avoid auto-generated classes like `.css-1x2y3z`.
3. Test it in the browser console: `document.querySelector(".product-price .amount").textContent`.
4. Put it in `selector`, and do the same for `stock_selector` if you want stock alerts.

Prices like `1.299,00 €`, `$1,299.99`, `1 299,00 zł`, `₹1,29,999` and `Rs. 2,499.00` are all understood. If the element has a `content` attribute (`<meta itemprop="price" content="12.99">`), that value is used.

## Data files

Both files are committed by the workflow as `github-actions[bot]` with the message `chore: update price data [skip ci]`. A file is only rewritten when something actually changed, so **unchanged prices mean no commit and no email.**

- **`data/state.json`**: per item: `last_price`, `last_currency`, `last_in_stock`, `consecutive_failures`, `error_alert_sent`, `last_error`, `price_below_active`, `drop_baseline_price`, `last_checked`, plus a top-level `last_digest_date`. `last_checked` is the time of the last check that *changed* the item's state, not of every run. That avoids a pointless commit every 6 hours. It's written atomically, with sorted keys.
- **`data/history.csv`**: `timestamp,item_id,name,price,currency,in_stock,source`. A row is added only when the price or stock changed, so the file stays small. Open it in a spreadsheet to chart prices.

To reset everything, replace `state.json` with `{}` and keep only the header line in `history.csv`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use no network and send no email. They use a fake fetcher that returns saved HTML pages (`tests/fixtures/`), a fake mailer that captures messages, and a fixed clock. They cover JSON-LD variants, selector fallback, price parsing, every alert rule, the failure counter, email categories, dry run, retrying after a failed send, config validation, and the acceptance test: **two runs with unchanged prices send zero emails and leave `state.json` and `history.csv` byte-identical.**

## Scrape responsibly

- **Check `robots.txt` and the site's terms of service.** `respect_robots_txt: true` (the default) skips disallowed pages. Only turn it off for sites you have permission to check.
- **Keep the frequency low.** Every 6 hours is plenty for prices. There's also a delay between requests to the same host (`request_delay_seconds`).
- **Identify yourself.** Requests send `User-Agent: python-price-drop-alerts/1.0 (+https://github.com/<owner>/python-price-drop-alerts)`. Replace `<owner>` in `src/price_alerts/fetch.py` with your GitHub username so site owners can see who's checking.
- **Don't scrape behind logins**, and don't try to work around blocks or CAPTCHAs.

## FAQ

**How do I get an email when a product's price drops?**
Add the product to `watchlist.yaml` with `target_price` (an alert when it hits your price) or `drop_percent` (an alert when it falls by that much), and add your `MAILTRAP_API_TOKEN` secret. The scheduled workflow checks every 6 hours and emails you once when the condition is met.

**How do I run a Python script on a schedule for free?**
Use GitHub Actions with an `on: schedule` cron trigger, as `.github/workflows/price-alerts.yml` does with `cron: "17 */6 * * *"`. Public repos get free Actions minutes, and private repos get a monthly free allowance. Pick an off-the-hour minute, because runs at `:00` are often delayed. The script keeps its memory by committing `data/` back to the repo, so it needs no database.

**How do I avoid sending the same alert twice?**
Store whether each condition already fired, and only alert on a change from false to true. Here, `price_below_active`, `drop_baseline_price`, `last_in_stock` and `error_alert_sent` in `data/state.json` record that. They're only updated after the email was sent successfully, so a failed send is retried instead of lost.

**How do I send email from a Python script?**
With the official Mailtrap SDK (`pip install mailtrap`):

```python
import os

import mailtrap as mt

client = mt.MailtrapClient(token=os.environ["MAILTRAP_API_TOKEN"])
client.send(mt.Mail(
    sender=mt.Address(email="alerts@yourdomain.com", name="Price Alerts"),
    to=[mt.Address(email="you@example.com")],
    subject="Price drop: Example Headphones 249.00 → 199.00 (-20%)",
    text="...", html="...", category="price-alert",
))
```

See `src/price_alerts/mailer.py`.

## Limitations

- **JavaScript-rendered prices.** The tool doesn't run a browser. If the price only appears after JavaScript runs and isn't in the JSON-LD, it can't see it. Many such sites still include JSON-LD in the HTML.
- **Sites that block bots.** Some shops return 403 or a CAPTCHA to non-browser clients or to cloud IP ranges, including GitHub's runners. You'll get a watcher-error email after 3 failures. Respect the block.
- **Scheduled workflows get disabled.** GitHub doesn't run scheduled workflows in forks until you enable Actions there, and disables them in public repos with no activity for 60 days. The bot's commits only happen when prices change. If the emails stop, check the Actions tab and re-enable the workflow.
- **Cron timing is approximate.** GitHub may delay scheduled runs at busy times.

## License

[MIT](LICENSE)
