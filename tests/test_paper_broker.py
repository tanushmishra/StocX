"""
Comprehensive Unit Tests for Stage 3: Paper Broker, Decimal Accounting,
Concurrency, Idempotency, and Risk Controls.
"""

from __future__ import annotations

from decimal import Decimal
import threading
import pytest

from engine.broker import (
    LiveBrokerStub,
    PaperBroker,
    build_order_proposal,
    get_fno_lot_size,
)


class TestLiveBrokerRefusal:
    """Security Gate: Verify LiveBrokerStub refuses all trading operations."""

    def test_live_broker_stub_raises_not_implemented(self):
        stub = LiveBrokerStub()
        with pytest.raises(NotImplementedError) as exc_info:
            stub.get_account("user-1")
        assert "Live broker trading is disabled" in str(exc_info.value)

        with pytest.raises(NotImplementedError) as exc_info:
            stub.place_orders("user-1", [], "idem-1")
        assert "Live broker trading is disabled" in str(exc_info.value)

        with pytest.raises(NotImplementedError) as exc_info:
            stub.get_positions("user-1")
        assert "Live broker trading is disabled" in str(exc_info.value)

        with pytest.raises(NotImplementedError) as exc_info:
            stub.close_position("user-1", "TCS.NS", 3500.0)
        assert "Live broker trading is disabled" in str(exc_info.value)


class TestIndependentDecimalAccounting:
    """
    Mathematical Precision Gate: Independent hand-calculated WAC and P&L verification.
    Calculation trace:
    1. Start: Cash = 100,000.00
    2. Buy 10 @ 3,000.00 -> Cost = 30,000.00 -> Cash = 70,000.00, WAC = 3,000.00, Qty = 10
    3. Buy 10 @ 3,500.00 -> Cost = 35,000.00 -> Cash = 35,000.00, WAC = (30,000+35,000)/20 = 3,250.00, Qty = 20
    4. Sell 15 @ 3,600.00 -> Proceeds = 54,000.00 -> Cash = 89,000.00
       Realized P&L = (3,600 - 3,250) * 15 = 350 * 15 = +5,250.00
       Remaining Qty = 5, Remaining WAC = 3,250.00
    """

    def test_hand_calculated_wac_and_realized_pnl(self):
        broker = PaperBroker()
        user_id = "test-wac-user"
        broker.set_risk_limits(user_id, max_order_value=100000.0)

        # Step 2: Buy 10 @ 3000
        res1 = broker.place_orders(
            user_id,
            [{"symbol": "TCS.NS", "side": "BUY", "qty": 10, "price": "3000.00"}],
            idempotency_key="step-2",
        )
        assert res1["success"] is True
        acct1 = broker.get_account(user_id)
        assert acct1["cash"] == "70000.00"
        pos1 = broker.get_positions(user_id)
        assert len(pos1) == 1
        assert pos1[0]["qty"] == 10
        assert pos1[0]["avg_price"] == "3000.00"

        # Step 3: Buy 10 @ 3500
        res2 = broker.place_orders(
            user_id,
            [{"symbol": "TCS.NS", "side": "BUY", "qty": 10, "price": "3500.00"}],
            idempotency_key="step-3",
        )
        assert res2["success"] is True
        acct2 = broker.get_account(user_id)
        assert acct2["cash"] == "35000.00"
        pos2 = broker.get_positions(user_id)
        assert pos2[0]["qty"] == 20
        assert pos2[0]["avg_price"] == "3250.00"

        # Step 4: Sell 15 @ 3600
        res3 = broker.place_orders(
            user_id,
            [{"symbol": "TCS.NS", "side": "SELL", "qty": 15, "price": "3600.00"}],
            idempotency_key="step-4",
        )
        assert res3["success"] is True
        acct3 = broker.get_account(user_id)
        assert acct3["cash"] == "89000.00"
        assert acct3["realized_pnl"] == "5250.00"
        pos3 = broker.get_positions(user_id)
        assert pos3[0]["qty"] == 5
        assert pos3[0]["avg_price"] == "3250.00"


class TestIdempotencyAndRiskControls:
    """Idempotency, stale pricing, order limits, and kill switch."""

    def test_duplicate_order_submission_is_idempotent(self):
        broker = PaperBroker()
        user_id = "test-idempotency-user"

        orders = [{"symbol": "INFY.NS", "side": "BUY", "qty": 10, "price": "1500.00"}]
        key = "unique-order-key-xyz"

        # First submit
        res1 = broker.place_orders(user_id, orders, idempotency_key=key)
        assert res1["success"] is True
        assert res1["is_duplicate"] is False
        assert broker.get_account(user_id)["cash"] == "85000.00"

        # Duplicate submit with identical idempotency key
        res2 = broker.place_orders(user_id, orders, idempotency_key=key)
        assert res2["success"] is True
        assert res2["is_duplicate"] is True
        # Cash must NOT be deducted again
        assert broker.get_account(user_id)["cash"] == "85000.00"

    def test_kill_switch_blocks_orders(self):
        broker = PaperBroker()
        user_id = "test-kill-switch-user"

        broker.set_kill_switch(user_id, active=True)
        orders = [{"symbol": "INFY.NS", "side": "BUY", "qty": 5, "price": "1500.00"}]
        res = broker.place_orders(user_id, orders, idempotency_key="kill-1")

        assert res["success"] is False
        assert "Kill switch is ACTIVE" in res["message"]
        assert broker.get_account(user_id)["cash"] == "100000.00"

    def test_max_order_value_exceeded_rejected(self):
        broker = PaperBroker()
        user_id = "test-max-value-user"
        broker.set_risk_limits(user_id, max_order_value=20000.0)

        # Order value = 10 * 3000 = 30,000 > 20,000
        orders = [{"symbol": "TCS.NS", "side": "BUY", "qty": 10, "price": "3000.00"}]
        res = broker.place_orders(user_id, orders, idempotency_key="val-1")

        assert res["success"] is False
        assert "exceeds max limit" in res["message"]

    def test_stale_data_flag_rejected(self):
        broker = PaperBroker()
        user_id = "test-stale-user"

        orders = [{"symbol": "TCS.NS", "side": "BUY", "qty": 5, "price": "3000.00", "is_stale": True}]
        res = broker.place_orders(user_id, orders, idempotency_key="stale-1")

        assert res["success"] is False
        assert "STALE" in res["message"]

    def test_insufficient_cash_rejected(self):
        broker = PaperBroker()
        user_id = "test-cash-user"

        # Requires 150,000, initial cash is 100,000
        broker.set_risk_limits(user_id, max_order_value=200000.0)
        orders = [{"symbol": "TCS.NS", "side": "BUY", "qty": 50, "price": "3000.00"}]
        res = broker.place_orders(user_id, orders, idempotency_key="cash-1")

        assert res["success"] is False
        assert "Insufficient cash balance" in res["message"]


class TestConcurrencySafety:
    """Thread safety: concurrent order submissions."""

    def test_multi_threaded_order_execution(self):
        broker = PaperBroker()
        user_id = "concurrent-user"
        num_threads = 10
        errors = []

        def worker(thread_idx: int):
            try:
                # Each buys 1 share of INFY.NS @ 1000.00
                res = broker.place_orders(
                    user_id,
                    [{"symbol": "INFY.NS", "side": "BUY", "qty": 1, "price": "1000.00"}],
                    idempotency_key=f"thread-{thread_idx}",
                )
                if not res["success"]:
                    errors.append(res["message"])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        acct = broker.get_account(user_id)
        # 100,000 - (10 * 1000) = 90,000.00
        assert acct["cash"] == "90000.00"
        positions = broker.get_positions(user_id)
        assert len(positions) == 1
        assert positions[0]["qty"] == 10
        assert positions[0]["avg_price"] == "1000.00"


class TestOrderProposalAndVerificationGuard:
    """Verification Guard: Rejected pairs never propose orders."""

    def test_rejected_pair_produces_no_orders(self):
        rejected_state = {
            "verification": {"verdict": "REJECTED", "details": "High hedged beta"},
            "portfolio": {"ticker_a": "TCS.NS", "ticker_b": "WIPRO.NS"},
        }
        proposal = build_order_proposal(rejected_state, capital=100000.0)
        assert proposal["eligible"] is False
        assert proposal["orders"] == []
        assert "REJECTED" in proposal["reason"]

    def test_approved_pair_generates_fno_sized_orders(self):
        approved_state = {
            "verification": {"verdict": "APPROVED"},
            "portfolio": {
                "ticker_a": "TCS.NS",
                "ticker_b": "WIPRO.NS",
                "weight_a": 0.5,
                "weight_b": 0.5,
                "price_a": 3500.0,
                "price_b": 450.0,
            },
        }
        proposal = build_order_proposal(approved_state, capital=100000.0)
        assert proposal["eligible"] is True
        assert len(proposal["orders"]) == 2

        order_a = proposal["orders"][0]
        order_b = proposal["orders"][1]

        assert order_a["symbol"] == "TCS.NS"
        assert order_a["side"] == "BUY"
        assert order_a["leg"] == "LONG"

        assert order_b["symbol"] == "WIPRO.NS"
        assert order_b["side"] == "SELL"
        assert order_b["leg"] == "SHORT"
        assert order_b["segment"] == "NSE_FNO_FUTURES"
        # Lot size for WIPRO.NS is defined as 1500 in config.py
        assert order_b["lot_size"] == 1500
        assert order_b["qty"] % 1500 == 0
