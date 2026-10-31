"""
Broker Interface and Paper Trading Implementation.
Stage 3: PaperBroker with Decimal P&L accounting, risk controls, idempotency,
F&O lot sizing, and LiveBrokerStub refusal.

Principles:
- Real trading is strictly disabled; LiveBrokerStub always raises NotImplementedError.
- Paper trading is default and clearly labeled "paper trading".
- All accounting math uses Python Decimal (no float rounding drift).
- Idempotent order execution via idempotency_key prevents duplicate order submissions.
- Risk controls (kill switch, STALE data check, max order value, cash sufficiency).
- Verification guard: Orders are NEVER proposed or executed for rejected pairs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
import logging
import threading
from typing import Any
import uuid

import config

logger = logging.getLogger(__name__)


def to_decimal(val: Any) -> Decimal:
    """Safely convert any numeric value or string to Decimal."""
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


class BrokerAdapter(ABC):
    """Abstract interface defining required broker operations."""

    @abstractmethod
    def get_account(self, user_id: str) -> dict[str, Any]:
        """Fetch virtual cash balance, positions, margin, and P&L."""
        pass

    @abstractmethod
    def place_orders(
        self,
        user_id: str,
        orders: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Place a list of orders idempotently."""
        pass

    @abstractmethod
    def get_positions(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch list of open positions."""
        pass

    @abstractmethod
    def close_position(self, user_id: str, symbol: str, current_price: Decimal | float) -> dict[str, Any]:
        """Close an active position at market price."""
        pass


class LiveBrokerStub(BrokerAdapter):
    """
    Live Broker Stub.
    Safety Guardrail: Refuses to execute live trades under all circumstances.
    """

    def __init__(self, broker_name: str = "Zerodha Kite"):
        self.broker_name = broker_name

    def get_account(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError("Live broker trading is disabled. Paper trading only.")

    def place_orders(
        self,
        user_id: str,
        orders: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        raise NotImplementedError("Live broker trading is disabled. Paper trading only.")

    def get_positions(self, user_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError("Live broker trading is disabled. Paper trading only.")

    def close_position(self, user_id: str, symbol: str, current_price: Decimal | float) -> dict[str, Any]:
        raise NotImplementedError("Live broker trading is disabled. Paper trading only.")


class PaperBroker(BrokerAdapter):
    """
    Deterministic Paper Broker with strict Decimal precision, thread-safe mutations,
    risk management limits, and idempotent order tracking.
    """

    DEFAULT_INITIAL_CASH = Decimal("100000.00")
    DEFAULT_MAX_ORDER_VALUE = Decimal("50000.00")
    DEFAULT_DAILY_LOSS_LIMIT = Decimal("10000.00")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Storage format: user_id -> account dict
        self._accounts: dict[str, dict[str, Any]] = {}

    def _get_or_create_account(self, user_id: str) -> dict[str, Any]:
        """Retrieve existing account or initialize default starting state."""
        if user_id not in self._accounts:
            self._accounts[user_id] = {
                "cash": self.DEFAULT_INITIAL_CASH,
                "realized_pnl": Decimal("0.00"),
                "positions": {},  # symbol -> {"qty": int, "avg_price": Decimal}
                "orders": {},     # idempotency_key -> result dict
                "risk_limits": {
                    "max_order_value": self.DEFAULT_MAX_ORDER_VALUE,
                    "daily_loss_limit": self.DEFAULT_DAILY_LOSS_LIMIT,
                    "kill_switch": False,
                },
            }
        return self._accounts[user_id]

    def set_kill_switch(self, user_id: str, active: bool) -> None:
        """Toggle emergency kill switch for a user account."""
        with self._lock:
            account = self._get_or_create_account(user_id)
            account["risk_limits"]["kill_switch"] = active

    def set_risk_limits(
        self,
        user_id: str,
        max_order_value: Decimal | float | None = None,
        daily_loss_limit: Decimal | float | None = None,
    ) -> None:
        """Update risk limits for a user account."""
        with self._lock:
            account = self._get_or_create_account(user_id)
            if max_order_value is not None:
                account["risk_limits"]["max_order_value"] = to_decimal(max_order_value)
            if daily_loss_limit is not None:
                account["risk_limits"]["daily_loss_limit"] = to_decimal(daily_loss_limit)

    def validate_order_risk(
        self,
        user_id: str,
        orders: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """
        Pre-flight risk validation:
        1. Emergency kill switch.
        2. Stale price data detection.
        3. Single order value limit.
        4. Cash balance sufficiency for buy orders.
        """
        account = self._get_or_create_account(user_id)
        limits = account["risk_limits"]

        if limits.get("kill_switch", False):
            return False, "Risk Gate: Kill switch is ACTIVE. All trading operations are halted."

        available_cash = account["cash"]
        total_buy_required = Decimal("0.00")

        for o in orders:
            symbol = o.get("symbol", "UNKNOWN")
            side = str(o.get("side", "")).upper()
            qty = int(o.get("qty", 0))
            price = to_decimal(o.get("price", "0"))

            if o.get("is_stale", False) or o.get("status") == "STALE":
                return False, f"Risk Gate: Order for {symbol} rejected because market price is STALE."

            if qty <= 0 or price <= 0:
                return False, f"Risk Gate: Invalid quantity ({qty}) or price ({price}) for {symbol}."

            order_value = price * Decimal(str(qty))
            if order_value > limits["max_order_value"]:
                return (
                    False,
                    f"Risk Gate: Order value INR {order_value:,.2f} for {symbol} exceeds max limit INR {limits['max_order_value']:,.2f}.",
                )

            if side == "BUY":
                total_buy_required += order_value

        if total_buy_required > available_cash:
            return (
                False,
                f"Risk Gate: Insufficient cash balance. Required: INR {total_buy_required:,.2f}, Available: INR {available_cash:,.2f}.",
            )

        return True, "PASS: Risk checks cleared."

    def place_orders(
        self,
        user_id: str,
        orders: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """
        Execute order set with idempotency check, risk limits, and Decimal accounting.
        """
        with self._lock:
            account = self._get_or_create_account(user_id)

            # Idempotency check: prevent duplicate submits
            if idempotency_key in account["orders"]:
                logger.info("Duplicate order submission detected for key %s", idempotency_key)
                existing = account["orders"][idempotency_key]
                return {
                    "success": True,
                    "is_duplicate": True,
                    "idempotency_key": idempotency_key,
                    "message": "Order already processed (idempotency preserved).",
                    "orders": existing["orders"],
                    "account": self._format_account_summary(user_id),
                }

            # Run pre-flight risk checks
            passed, reason = self.validate_order_risk(user_id, orders)
            if not passed:
                return {
                    "success": False,
                    "is_duplicate": False,
                    "idempotency_key": idempotency_key,
                    "message": reason,
                    "orders": [],
                    "account": self._format_account_summary(user_id),
                }

            # Process execution
            executed_orders: list[dict[str, Any]] = []
            for o in orders:
                symbol = str(o["symbol"])
                side = str(o["side"]).upper()
                qty = int(o["qty"])
                price = to_decimal(o["price"])
                order_value = price * Decimal(str(qty))

                pos = account["positions"].get(symbol, {"qty": 0, "avg_price": Decimal("0.00")})
                cur_qty = pos["qty"]
                cur_avg = pos["avg_price"]

                if side == "BUY":
                    account["cash"] -= order_value
                    if cur_qty < 0:
                        # Covering an existing short position
                        cover_qty = min(qty, abs(cur_qty))
                        pnl = (cur_avg - price) * Decimal(str(cover_qty))
                        account["realized_pnl"] += pnl
                        rem_buy = qty - cover_qty
                        new_qty = cur_qty + cover_qty
                        if rem_buy > 0:
                            # Reverses into a long position
                            new_qty = rem_buy
                            new_avg = price
                        else:
                            new_avg = cur_avg if new_qty != 0 else Decimal("0.00")
                    else:
                        # Adding to or opening long position
                        new_qty = cur_qty + qty
                        new_cost = (Decimal(str(cur_qty)) * cur_avg) + order_value
                        new_avg = new_cost / Decimal(str(new_qty))

                    account["positions"][symbol] = {
                        "qty": new_qty,
                        "avg_price": new_avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    }

                elif side == "SELL":
                    account["cash"] += order_value
                    if cur_qty > 0:
                        # Closing an existing long position
                        close_qty = min(qty, cur_qty)
                        pnl = (price - cur_avg) * Decimal(str(close_qty))
                        account["realized_pnl"] += pnl
                        rem_sell = qty - close_qty
                        new_qty = cur_qty - close_qty
                        if rem_sell > 0:
                            # Reverses into a short position
                            new_qty = -rem_sell
                            new_avg = price
                        else:
                            new_avg = cur_avg if new_qty != 0 else Decimal("0.00")
                    else:
                        # Adding to or opening short position
                        new_qty = cur_qty - qty  # negative quantity
                        abs_new_qty = abs(new_qty)
                        new_cost = (Decimal(str(abs(cur_qty))) * cur_avg) + order_value
                        new_avg = new_cost / Decimal(str(abs_new_qty))

                    account["positions"][symbol] = {
                        "qty": new_qty,
                        "avg_price": new_avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    }

                # Clean up flat positions
                if account["positions"][symbol]["qty"] == 0:
                    del account["positions"][symbol]

                executed_orders.append({
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "price": str(price),
                    "order_value": str(order_value.quantize(Decimal("0.01"))),
                    "status": "FILLED",
                })

            result = {
                "success": True,
                "is_duplicate": False,
                "idempotency_key": idempotency_key,
                "message": f"Successfully placed {len(executed_orders)} paper orders.",
                "orders": executed_orders,
            }
            account["orders"][idempotency_key] = result
            result["account"] = self._format_account_summary(user_id)
            return result

    def get_positions(self, user_id: str) -> list[dict[str, Any]]:
        """Return list of active open positions."""
        with self._lock:
            account = self._get_or_create_account(user_id)
            pos_list = []
            for sym, data in account["positions"].items():
                pos_list.append({
                    "symbol": sym,
                    "qty": data["qty"],
                    "avg_price": str(data["avg_price"]),
                })
            return pos_list

    def close_position(self, user_id: str, symbol: str, current_price: Decimal | float) -> dict[str, Any]:
        """Close an active position at current market price."""
        with self._lock:
            account = self._get_or_create_account(user_id)
            if symbol not in account["positions"]:
                return {"success": False, "message": f"No open position found for {symbol}."}

            pos = account["positions"][symbol]
            qty = pos["qty"]
            price = to_decimal(current_price)
            order_side = "SELL" if qty > 0 else "BUY"
            order_qty = abs(qty)

            # Generate close order and execute
            close_order = {
                "symbol": symbol,
                "side": order_side,
                "qty": order_qty,
                "price": price,
            }

        # Release lock to call place_orders
        return self.place_orders(user_id, [close_order], idempotency_key=f"close-{symbol}-{uuid.uuid4().hex[:8]}")

    def _format_account_summary(self, user_id: str) -> dict[str, Any]:
        """Format account details for UI and API consumers."""
        account = self._accounts[user_id]
        cash = account["cash"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        realized_pnl = account["realized_pnl"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        positions_summary = []
        for sym, d in account["positions"].items():
            positions_summary.append({
                "symbol": sym,
                "qty": d["qty"],
                "avg_price": str(d["avg_price"]),
            })

        return {
            "cash": str(cash),
            "realized_pnl": str(realized_pnl),
            "positions_count": len(positions_summary),
            "positions": positions_summary,
            "kill_switch": account["risk_limits"]["kill_switch"],
        }

    def get_account(self, user_id: str) -> dict[str, Any]:
        """Public method to fetch user account ledger summary."""
        with self._lock:
            self._get_or_create_account(user_id)
            return self._format_account_summary(user_id)


# Global singleton instance of PaperBroker
paper_broker = PaperBroker()


def get_fno_lot_size(symbol: str) -> int:
    """Retrieve F&O contract lot size for NSE derivatives."""
    lot = config.FNO_LOT_SIZES.get(symbol)
    if lot is not None:
        return int(lot)

    try:
        from engine.data_fetcher import get_fno_lot_sizes
        all_lots = get_fno_lot_sizes()
        if symbol in all_lots:
            return int(all_lots[symbol])
    except Exception:
        pass

    return 1


def build_order_proposal(
    hedge_state: dict[str, Any],
    capital: float = 100000.0,
) -> dict[str, Any]:
    """
    Build proposed order set from hedge pipeline state.

    Zero-Hallucination & Risk Guardrails:
    - If verification verdict is NOT 'APPROVED', strictly returns NO orders.
    - Shorts in cash segment cannot be carried overnight on NSE; short leg is sized
      by F&O lot sizing.
    - Requires explicit human confirmation before dispatch.
    """
    verification = hedge_state.get("verification", {})
    verdict = verification.get("verdict", "")
    if verdict != "APPROVED":
        return {
            "eligible": False,
            "verdict": verdict or "REJECTED",
            "reason": (
                "Verification verdict is REJECTED. Under zero-hallucination quant rules, "
                "rejected pairs cannot generate trading orders."
            ),
            "orders": [],
            "idempotency_key": None,
        }

    portfolio = hedge_state.get("portfolio", {})
    ticker_a = portfolio.get("ticker_a")
    ticker_b = portfolio.get("ticker_b")
    weight_a = portfolio.get("weight_a", 0.5)
    weight_b = portfolio.get("weight_b", 0.5)
    price_a = portfolio.get("price_a", 1000.0)
    price_b = portfolio.get("price_b", 1000.0)

    if not ticker_a or not ticker_b or price_a <= 0 or price_b <= 0:
        return {
            "eligible": False,
            "verdict": "APPROVED",
            "reason": "Missing constituent ticker or price data for order proposal.",
            "orders": [],
            "idempotency_key": None,
        }

    # Calculate capital allocation per leg
    cap_dec = to_decimal(capital)
    alloc_a = cap_dec * to_decimal(weight_a)
    alloc_b = cap_dec * to_decimal(weight_b)

    # Long leg: cash equity quantity
    qty_a = max(1, int(alloc_a / to_decimal(price_a)))

    # Short leg: mapped to F&O lot size
    lot_size_b = get_fno_lot_size(ticker_b)
    raw_qty_b = int(alloc_b / to_decimal(price_b))
    # Round to nearest lot size (at least 1 lot)
    num_lots_b = max(1, round(raw_qty_b / lot_size_b))
    qty_b = num_lots_b * lot_size_b

    order_a = {
        "symbol": ticker_a,
        "side": "BUY",
        "qty": qty_a,
        "price": float(to_decimal(price_a).quantize(Decimal("0.01"))),
        "leg": "LONG",
        "segment": "EQUITY_CASH",
        "lot_size": 1,
    }

    order_b = {
        "symbol": ticker_b,
        "side": "SELL",
        "qty": qty_b,
        "price": float(to_decimal(price_b).quantize(Decimal("0.01"))),
        "leg": "SHORT",
        "segment": "NSE_FNO_FUTURES",
        "lot_size": lot_size_b,
        "lots": num_lots_b,
    }

    idempotency_key = f"prop-{ticker_a}-{ticker_b}-{int(capital)}-{uuid.uuid4().hex[:8]}"

    return {
        "eligible": True,
        "verdict": "APPROVED",
        "orders": [order_a, order_b],
        "idempotency_key": idempotency_key,
        "capital_allocated": capital,
        "notes": f"Short leg {ticker_b} mapped to {num_lots_b} F&O lot(s) (lot size {lot_size_b}).",
    }
