# backend/agents/base_agent.py
# Abstract base class for all agents.
# Provides shared helpers: retain_memory(), recall_memory(), ask().
# Every concrete agent inherits this so they all read/write the same project memory.
