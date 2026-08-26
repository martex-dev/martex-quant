"""Risk management: the gate every exposure passes through.

Nothing reaches execution without going through a RiskPolicy. Phase 2 ships
only the passthrough policy; real sizing/drawdown/kill-switch policies are
Phase 4 scope.
"""
