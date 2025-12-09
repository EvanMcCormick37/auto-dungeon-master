"""
Storage layer for the dungeon crawler game.

Provides:
- SQLite database for relational data (entities, items, spells, saves)
- NetworkX graph for entity relationships and spatial navigation
- LanceDB vector store for semantic search (RAG)
"""

from src.game.storage.database import Database, to_json, from_json, SCHEMA_VERSION
from src.game.storage.graph.world_graph import WorldGraph, NodeType, EdgeType
from src.game.storage.vectors.lance_store import (
    VectorStore,
    VectorCollection,
    SearchResult,
    # Document types
    RulesDocument,
    LoreDocument,
    DMStyleDocument,
    ActionDocument,
    ItemDocument,
    EntityDocument,
    SpellDocument,
)

__all__ = [
    # Database
    "Database",
    "to_json",
    "from_json",
    "SCHEMA_VERSION",
    # Graph
    "WorldGraph",
    "NodeType",
    "EdgeType",
    # Vector Store
    "VectorStore",
    "VectorCollection",
    "SearchResult",
    # Document types
    "RulesDocument",
    "LoreDocument",
    "DMStyleDocument",
    "ActionDocument",
    "ItemDocument",
    "EntityDocument",
    "SpellDocument",
]
