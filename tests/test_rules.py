from decimal import Decimal as D

from price_alerts.models import FetchResult, Item
from price_alerts.rules import (
    apply_sent,
    check_back_in_stock,
    check_drop_percent,
    check_price_below,
    evaluate,
)
from price_alerts.state import ItemState


def item(**kwargs) -> Item:
    data = {"name": "Thing", "url": "https://shop.example/p/1"}
    data.update(kwargs)
    return Item.model_validate(data)


def ok(price: str | None, in_stock: bool | None = True) -> FetchResult:
    return FetchResult(ok=True, price=None if price is None else D(price), currency="EUR",
                       in_stock=in_stock, source="json-ld")


def step(it: Item, state: ItemState, result: FetchResult) -> tuple[ItemState, list[str]]:
    """Evaluate and pretend every alert was sent."""
    ev = evaluate(it, state, result)
    new = ev.state
    for alert in ev.alerts:
        new = apply_sent(new, alert)
    return new, [a.kind for a in ev.alerts]


# --- pure helpers ---------------------------------------------------------------------------


def test_check_price_below():
    assert check_price_below(D("90"), D("100"), active=False) == (True, False)
    assert check_price_below(D("100"), D("100"), active=False) == (True, False)
    assert check_price_below(D("90"), D("100"), active=True) == (False, False)
    assert check_price_below(D("101"), D("100"), active=True) == (False, True)


def test_check_drop_percent():
    assert check_drop_percent(D("100"), None, D("10")) == (False, D("100"))
    assert check_drop_percent(D("95"), D("100"), D("10")) == (False, D("100"))
    assert check_drop_percent(D("90"), D("100"), D("10")) == (True, D("100"))
    assert check_drop_percent(D("120"), D("100"), D("10")) == (False, D("120"))


def test_check_back_in_stock():
    assert check_back_in_stock(True, False) is True
    assert check_back_in_stock(True, None) is False
    assert check_back_in_stock(True, True) is False
    assert check_back_in_stock(False, False) is False


# --- price_below ----------------------------------------------------------------------------


def test_price_below_fires_once_and_rearms_after_going_above_target():
    it = item(target_price=200, notify_on=["price_below"])
    s = ItemState()

    s, kinds = step(it, s, ok("250"))
    assert kinds == []
    s, kinds = step(it, s, ok("199"))
    assert kinds == ["price_below"] and s.price_below_active
    s, kinds = step(it, s, ok("199"))
    assert kinds == []
    s, kinds = step(it, s, ok("180"))
    assert kinds == []  # still below; already told
    s, kinds = step(it, s, ok("210"))
    assert kinds == [] and not s.price_below_active
    s, kinds = step(it, s, ok("195"))
    assert kinds == ["price_below"]


def test_price_below_can_fire_on_first_observation():
    it = item(target_price=300, notify_on=["price_below"])
    _, kinds = step(it, ItemState(), ok("250"))
    assert kinds == ["price_below"]


def test_price_below_not_marked_when_send_fails():
    it = item(target_price=300, notify_on=["price_below"])
    ev = evaluate(it, ItemState(), ok("250"))
    assert ev.state.price_below_active is False  # only set by apply_sent
    assert evaluate(it, ev.state, ok("250")).alerts[0].kind == "price_below"


# --- drop_percent ---------------------------------------------------------------------------


def test_drop_percent_baseline_behaviour():
    it = item(drop_percent=10, notify_on=["drop_percent"])
    s = ItemState()

    s, kinds = step(it, s, ok("100"))
    assert kinds == [] and s.drop_baseline_price == D("100")  # never on first observation
    s, kinds = step(it, s, ok("95"))
    assert kinds == [] and s.drop_baseline_price == D("100")
    s, kinds = step(it, s, ok("90"))
    assert kinds == ["drop_percent"] and s.drop_baseline_price == D("90")
    s, kinds = step(it, s, ok("90"))
    assert kinds == []
    s, kinds = step(it, s, ok("85"))
    assert kinds == []  # only 5.6% below the new baseline
    s, kinds = step(it, s, ok("120"))
    assert kinds == [] and s.drop_baseline_price == D("120")  # rise moves baseline up
    s, kinds = step(it, s, ok("108"))
    assert kinds == ["drop_percent"]


def test_drop_percent_alert_reports_baseline_as_old_price():
    it = item(drop_percent=20, notify_on=["drop_percent"])
    ev = evaluate(it, ItemState(last_price=D("240"), drop_baseline_price=D("250")), ok("199"))
    alert = ev.alerts[0]
    assert alert.old_price == D("250") and alert.price == D("199.00")
    assert round(alert.change_percent) == -20


# --- back_in_stock --------------------------------------------------------------------------


def test_back_in_stock_only_on_false_to_true():
    it = item(notify_on=["back_in_stock"])
    s = ItemState()

    s, kinds = step(it, s, ok("10", in_stock=True))
    assert kinds == []  # first observation
    s, kinds = step(it, s, ok("10", in_stock=False))
    assert kinds == [] and s.last_in_stock is False
    s, kinds = step(it, s, ok("10", in_stock=None))
    assert kinds == [] and s.last_in_stock is False  # unknown keeps the last known value
    s, kinds = step(it, s, ok("10", in_stock=True))
    assert kinds == ["back_in_stock"] and s.last_in_stock is True
    s, kinds = step(it, s, ok("10", in_stock=True))
    assert kinds == []


def test_back_in_stock_not_from_unknown():
    it = item(notify_on=["back_in_stock"])
    _, kinds = step(it, ItemState(last_in_stock=None), ok("10", in_stock=True))
    assert kinds == []


def test_back_in_stock_retries_if_not_sent():
    it = item(notify_on=["back_in_stock"])
    ev = evaluate(it, ItemState(last_in_stock=False), ok("10", in_stock=True))
    assert ev.state.last_in_stock is False
    assert [a.kind for a in evaluate(it, ev.state, ok("10", in_stock=True)).alerts] == ["back_in_stock"]


# --- failures -------------------------------------------------------------------------------


def test_failure_keeps_price_and_counts():
    it = item(notify_on=["back_in_stock"])
    s = ItemState(last_price=D("10.00"), last_in_stock=True)
    s, kinds = step(it, s, FetchResult.failure("HTTP 500"))
    assert kinds == []
    assert (s.last_price, s.last_in_stock, s.consecutive_failures, s.last_error) == (
        D("10.00"), True, 1, "HTTP 500",
    )


def test_failure_threshold_alerts_once_and_success_resets():
    it = item(notify_on=["back_in_stock"])
    s = ItemState()
    fired = []
    for _ in range(5):
        s, kinds = step(it, s, FetchResult.failure("boom"))
        fired.append(kinds)
    assert fired == [[], [], ["watcher_error"], [], []]
    assert s.error_alert_sent and s.consecutive_failures == 5

    s, kinds = step(it, s, ok("10"))
    assert kinds == [] and s.consecutive_failures == 0 and not s.error_alert_sent and s.last_error is None
