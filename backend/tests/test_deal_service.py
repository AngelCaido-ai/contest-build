import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.enums import DealStatus
from app.services.deal_service import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    set_status,
)


class TestSetStatusEnforce(unittest.TestCase):
    def _make_deal(self, status: DealStatus):
        return SimpleNamespace(id=1, status=status)

    def test_valid_transitions(self):
        for current, targets in ALLOWED_TRANSITIONS.items():
            for target in targets:
                deal = self._make_deal(current)
                set_status(deal, target)
                self.assertEqual(deal.status, target)

    def test_invalid_transition_raises(self):
        deal = self._make_deal(DealStatus.RELEASED)
        with self.assertRaises(InvalidTransitionError):
            set_status(deal, DealStatus.NEGOTIATING)

    def test_terminal_states_reject_all(self):
        for terminal in [DealStatus.RELEASED, DealStatus.REFUNDED, DealStatus.CANCELED]:
            deal = self._make_deal(terminal)
            for target in DealStatus:
                if target == terminal:
                    continue
                with self.assertRaises(InvalidTransitionError):
                    set_status(deal, target)

    def test_same_status_raises(self):
        deal = self._make_deal(DealStatus.FUNDED)
        with self.assertRaises(InvalidTransitionError):
            set_status(deal, DealStatus.FUNDED)

    def test_error_attributes(self):
        deal = self._make_deal(DealStatus.RELEASED)
        try:
            set_status(deal, DealStatus.NEGOTIATING)
        except InvalidTransitionError as exc:
            self.assertEqual(exc.deal_id, 1)
            self.assertEqual(exc.current, DealStatus.RELEASED)
            self.assertEqual(exc.target, DealStatus.NEGOTIATING)
            self.assertIn("RELEASED", str(exc))
            self.assertIn("NEGOTIATING", str(exc))
        else:
            self.fail("InvalidTransitionError not raised")

    def test_inherits_value_error(self):
        deal = self._make_deal(DealStatus.RELEASED)
        with self.assertRaises(ValueError):
            set_status(deal, DealStatus.NEGOTIATING)
