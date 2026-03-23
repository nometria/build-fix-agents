"""
Base agent abstraction. Subclass BaseAgent to add new fixers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentEdit:
    """A single edit to apply to a file."""
    file_path: str   # relative to project root
    old_string: str
    new_string: str
    description: str = ""


@dataclass
class AgentResult:
    """Result of running an agent."""
    success: bool
    edits: List[AgentEdit] = field(default_factory=list)
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all build-fix agents.
    Subclass and override `run()` for new fixers (SEO, perf, security, etc.).
    """
    name: str = "base"
    description: str = ""

    @abstractmethod
    def run(
        self,
        project_root: Path,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Run the agent. Return proposed edits and/or a message."""
        pass
