"""Unit tests for agents/state.py and StateProxy behavior."""

import copy
import pytest
from typing import Any

from agents.state import HedgeBuilderState, StateProxy, STATE_SCHEMA_DEFAULTS, wrap_state


class TestStateProxyBehavior:
    """Tests verifying StateProxy contracts, dual access, and mutation safety."""

    def test_default_initialization_contains_all_schema_keys(self):
        proxy = StateProxy()
        for key in STATE_SCHEMA_DEFAULTS:
            assert key in proxy
            assert hasattr(proxy, key)
            assert getattr(proxy, key) == STATE_SCHEMA_DEFAULTS[key]

    def test_dual_access_dot_and_bracket(self):
        proxy = StateProxy(thesis="Tech leaders long", attempt_count=2, approved=True)
        # Dot access
        assert proxy.thesis == "Tech leaders long"
        assert proxy.attempt_count == 2
        assert proxy.approved is True

        # Bracket access
        assert proxy["thesis"] == "Tech leaders long"
        assert proxy["attempt_count"] == 2
        assert proxy["approved"] is True

        # get method
        assert proxy.get("thesis") == "Tech leaders long"
        assert proxy.get("attempt_count") == 2
        assert proxy.get("non_existent", "default_val") == "default_val"

    def test_dot_mutation_updates_item(self):
        proxy = StateProxy()
        proxy.selected_long = "TCS.NS"
        proxy.selected_short = "WIPRO.NS"
        proxy.approved = True

        assert proxy["selected_long"] == "TCS.NS"
        assert proxy["selected_short"] == "WIPRO.NS"
        assert proxy["approved"] is True

    def test_item_mutation_updates_dot(self):
        proxy = StateProxy()
        proxy["selected_long"] = "INFY.NS"
        proxy["attempt_count"] = 3

        assert proxy.selected_long == "INFY.NS"
        assert proxy.attempt_count == 3

    def test_nested_collection_mutation_isolation(self):
        """Mutating nested lists/dicts on a proxy copy must not corrupt the original."""
        source_data = {
            "rejection_log": [{"long": "INFY.NS", "short": "WIPRO.NS", "reason": "Failed coint"}],
            "pair_metrics": {"static_beta_long": 1.05},
        }
        proxy1 = StateProxy(source_data)
        proxy2 = StateProxy(proxy1)

        # Mutate proxy2 nested structures
        proxy2.rejection_log.append({"long": "TCS.NS", "short": "TECHM.NS", "reason": "High beta"})
        proxy2.pair_metrics["static_beta_long"] = 0.95

        # Verify proxy1 remained intact
        assert len(proxy1.rejection_log) == 1
        assert len(proxy2.rejection_log) == 2
        assert proxy1.pair_metrics["static_beta_long"] == 1.05
        assert proxy2.pair_metrics["static_beta_long"] == 0.95

    def test_wrap_state_idempotency(self):
        proxy = StateProxy({"thesis": "Macro view"})
        wrapped = wrap_state(proxy)
        assert wrapped is proxy

    def test_wrap_state_handles_dict_and_object(self):
        class MockObjectState:
            thesis = "Object thesis"
            target_sector = "NIFTY BANK"
            attempt_count = 1

        obj = MockObjectState()
        proxy_from_obj = wrap_state(obj)
        assert isinstance(proxy_from_obj, StateProxy)
        assert proxy_from_obj.thesis == "Object thesis"
        assert proxy_from_obj.target_sector == "NIFTY BANK"
        assert proxy_from_obj.attempt_count == 1
        # Unprovided schema fields default safely
        assert proxy_from_obj.lookback_days == 252
        assert proxy_from_obj.benchmark == "^NSEI"

    def test_wrap_state_handles_none_and_empty(self):
        p1 = wrap_state(None)
        assert isinstance(p1, StateProxy)
        assert p1.thesis == ""

        p2 = wrap_state({})
        assert isinstance(p2, StateProxy)
        assert p2.benchmark == "^NSEI"

    def test_to_dict_and_to_state_conversion(self):
        proxy = StateProxy(thesis="Test thesis", approved=True)
        d = proxy.to_dict()
        assert isinstance(d, dict)
        assert d["thesis"] == "Test thesis"
        assert d["approved"] is True

        state = proxy.to_state()
        assert isinstance(state, dict)
        assert state["thesis"] == "Test thesis"

    def test_attribute_error_on_undefined_attribute(self):
        proxy = StateProxy()
        with pytest.raises(AttributeError):
            _ = proxy.completely_unknown_attribute_name_xyz
