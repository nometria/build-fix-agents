from .base import AgentEdit, AgentResult, BaseAgent
from .duplicate_var import DuplicateVarAgent
from .missing_export import MissingExportAgent
from .export_spelling import ExportSpellingAgent
from .unused_import import UnusedImportAgent

__all__ = [
    "AgentEdit", "AgentResult", "BaseAgent",
    "DuplicateVarAgent", "MissingExportAgent",
    "ExportSpellingAgent", "UnusedImportAgent",
]


def get_all_agents():
    """Return default agent pipeline (order matters — unused import first)."""
    return [
        UnusedImportAgent(),
        DuplicateVarAgent(),
        MissingExportAgent(),
        ExportSpellingAgent(),
    ]
