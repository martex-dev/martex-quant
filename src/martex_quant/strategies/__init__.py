"""Strategies: pure signal generators.

A strategy maps market history to a target exposure in [-1, +1]. It never
sizes positions, never creates orders, never sees account state — that is
portfolio and risk territory, by design.
"""
