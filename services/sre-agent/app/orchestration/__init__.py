"""Orchestration layer — multi-agent topology built on LangGraph subgraphs.

The orchestrator owns CaseState. Each agent is a compiled subgraph that
receives an immutable projection of CaseState and returns an AgentEvent.

See ARCHITECTURE.md §"Agent Orchestration Layer" for the contract.
"""
