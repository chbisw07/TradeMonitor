"""Safety tests for the TM1/TGT2 read-only broker contract."""

from trademonitor.brokers.base import Broker


def test_tgt2_broker_contract_has_no_write_operations() -> None:
    prohibited = {
        "place_order",
        "submit_order",
        "modify_order",
        "cancel_order",
        "exit_position",
    }
    assert prohibited.isdisjoint(set(dir(Broker)))
