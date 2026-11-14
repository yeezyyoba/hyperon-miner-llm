"""Shim imported by PeTTa: ``!(import! &self minerllm_bridge.py)``.

PeTTa's py-call resolves ``module.function`` with exactly one dot, so it can't
call ``minerllm.bridge.select`` directly. This module puts the repository root on
sys.path and re-exports the bridge functions under a single-dot name, the same
pattern upstream uses for boost_petta.py.
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from minerllm.bridge import configure, finish, select, verify_finished, verify_started  # noqa: E402,F401
