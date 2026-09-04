"""Broker integration package."""

from trademonitor.brokers.execution_simulator import SimulatedExecutionBroker, SubmitFault

# Optional real-broker adapter; import directly from trademonitor.brokers.zerodha when configured.
