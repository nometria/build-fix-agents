"""build-fix — auto-repair TypeScript/JS build errors."""
from .fixer import apply_build_fix
from .agents import get_all_agents, AgentEdit, AgentResult, BaseAgent

__all__ = ["apply_build_fix", "get_all_agents", "AgentEdit", "AgentResult", "BaseAgent"]
__version__ = "0.1.0"
