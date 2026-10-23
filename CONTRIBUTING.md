# Contributing to python-price-drop-alerts

Thanks for taking the time to contribute. Bug reports, ideas, documentation fixes and code are all welcome. This guide takes you from cloning the repo to an opened pull request.

## Ways to help

- Report a bug or suggest a feature by opening an issue. Say what you expected, what happened, and the steps to reproduce it.
- Improve the README or the docs.
- Pick up an open issue. Issues labelled `good first issue` are a good place to start.

## Picking up an issue

1. Browse the open issues and choose one.
2. Comment on it to say you'd like to work on it, and wait for a maintainer to reply before you start.
3. Work on one issue at a time.
4. If you can't finish, say so in the issue so someone else can take it.

If you want to work on something that has no issue yet, open one first and describe your idea, so you don't spend time on a change that doesn't fit.

## Set up

You need Python 3.12.

```bash
git clone https://github.com/<your-username>/python-price-drop-alerts.git && cd python-price-drop-alerts
python3.12 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Add your `MAILTRAP_API_TOKEN` to `.env` only if you want to send real emails. **The tests need no credentials and no network.**

## Run it

Start with a dry run. It fetches and evaluates every product in `watchlist.yaml`, saves each email as HTML in `out/`, sends nothing and leaves `data/` untouched:

```bash
python -m price_alerts --dry-run -v
```

To try the dashboard on your own machine:

```bash
python -m price_alerts ui --open
```

`data/` is updated by the scheduled workflow, and `watchlist.yaml` is the owner's own product list, so please don't include changes to either of them in a pull request.

## Tests and checks

```bash
pytest                          # no network or credentials needed
ruff check .                    # lint, including the security rules
pip-audit -r requirements.txt   # known vulnerabilities in dependencies
```

The tests use `httpx.MockTransport` and a fake mailer. HTML fixtures for extraction live in `tests/fixtures/`.

Please add or update tests for the behavior you change, and run all the checks above before you open a pull request.

## Making your change

1. Fork the repository and create a branch from `main`. Use a short name that says what it does, such as `fix/expired-code-message`, `feature/dark-theme` or `docs/readme-typo`.
2. Keep each pull request focused on one change. Don't mix refactoring or formatting changes into it.
3. Write commit messages as a short, imperative summary of what changed (for example `Fix wrong time in reminder email`), and add a few lines of explanation if the reason isn't obvious.
4. Push your branch and open a pull request against `main`.

A good pull request description says:

- what the change does and why it is needed;
- how you tested it;
- which issue it closes, written as `Closes #123`;
- screenshots for any change to the user interface.

## Project layout

- `src/price_alerts/`: fetching, extraction, alert rules, state, email templates and the CLI.
- `src/price_alerts/web/`: the local dashboard.
- `tests/`: the test suite, with HTML fixtures in `tests/fixtures/`.
- `watchlist.yaml` and `data/`: the product list, and the saved prices and alert state that the scheduled workflow updates.

## Keep secrets out

Never put API tokens, `.env` contents or real customer data in an issue, a pull request or a commit. `.env` is git-ignored, and the example file only contains placeholders.

## License

By contributing, you agree that your contributions are licensed under the project's [MIT license](LICENSE).
