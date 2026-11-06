# tests/test_memory_service.py
# Tests for the memory_service orchestration layer.
# Covers: retain → recall round-trip, ask returns a grounded answer,
#         graceful degradation when Hindsight is unavailable.
