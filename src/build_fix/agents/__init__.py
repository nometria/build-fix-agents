from .base import AgentEdit, AgentResult, BaseAgent
from .duplicate_var import DuplicateVarAgent
from .missing_export import MissingExportAgent
from .export_spelling import ExportSpellingAgent
from .unused_import import UnusedImportAgent
from .implicit_any import ImplicitAnyAgent
from .missing_return_type import MissingReturnTypeAgent

__all__ = [
    "AgentEdit", "AgentResult", "BaseAgent",
    "DuplicateVarAgent", "MissingExportAgent",
    "ExportSpellingAgent", "UnusedImportAgent",
    "ImplicitAnyAgent", "MissingReturnTypeAgent",
]


def get_all_agents():
    """Return default agent pipeline (order matters -- unused import first)."""
    return [
        UnusedImportAgent(),
        DuplicateVarAgent(),
        MissingExportAgent(),
        ExportSpellingAgent(),
        ImplicitAnyAgent(),
        MissingReturnTypeAgent(),
    ]
