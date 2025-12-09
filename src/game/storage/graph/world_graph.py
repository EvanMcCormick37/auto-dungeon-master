"""
WorldGraph: NetworkX-based graph database for entity relationships.

Manages spatial relationships (rooms, doors, levels) and narrative relationships
(characters, lore, story beats) using a directed multigraph.
"""

import pickle
import json
from pathlib import Path
from typing import Any, Literal
from dataclasses import dataclass
from enum import Enum

import networkx as nx


class NodeType(str, Enum):
    """Types of nodes in the world graph."""
    LEVEL = "level"
    ROOM = "room"
    DOOR = "door"
    ENTITY = "entity"          # Monsters, NPCs, creatures
    ITEM = "item"
    MACGUFFIN = "macguffin"
    LORE = "lore"
    TRAP = "trap"
    PLAYER = "player"


class EdgeType(str, Enum):
    """Types of relationships between nodes."""
    # Spatial relationships
    CONTAINS = "contains"           # level -> room, room -> item
    CONNECTS_TO = "connects_to"     # room <-> room (via door)
    LEADS_TO = "leads_to"           # door -> room
    
    # Entity relationships
    LOCATED_IN = "located_in"       # entity -> room
    OWNS = "owns"                   # entity -> item
    EQUIPPED = "equipped"           # entity -> item
    
    # Narrative relationships
    KNOWS = "knows"                 # entity -> entity (acquaintance)
    KNOWS_ABOUT = "knows_about"     # entity -> lore/macguffin
    INVOLVES = "involves"           # lore -> entity/item/location
    RELATED_TO = "related_to"       # lore <-> lore
    
    # Story progression
    TRIGGERS = "triggers"           # lore(moment) -> lore(moment)
    REQUIRES = "requires"           # action -> requirement
    GUARDS = "guards"               # entity -> door/item/room
    
    # Trap relationships
    PROTECTS = "protects"           # trap -> room/door/item


@dataclass
class GraphNode:
    """Wrapper for graph node data."""
    id: str
    node_type: NodeType
    name: str | None = None
    data: dict | None = None


@dataclass 
class GraphEdge:
    """Wrapper for graph edge data."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    data: dict | None = None


class WorldGraph:
    """
    NetworkX-based graph for managing world relationships.
    
    Uses a directed multigraph to support:
    - Multiple edge types between same nodes
    - Directional relationships (A knows_about B ≠ B knows_about A)
    - Rich metadata on nodes and edges
    """
    
    def __init__(self):
        """Initialize empty world graph."""
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()
    
    @property
    def graph(self) -> nx.MultiDiGraph:
        """Access underlying NetworkX graph."""
        return self._graph
    
    # =========================================================================
    # NODE OPERATIONS
    # =========================================================================
    
    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        name: str | None = None,
        **attributes
    ) -> None:
        """
        Add a node to the graph.
        
        Args:
            node_id: Unique identifier for the node
            node_type: Type of node (level, room, entity, etc.)
            name: Display name
            **attributes: Additional node attributes
        """
        self._graph.add_node(
            node_id,
            node_type=node_type.value,
            name=name,
            **attributes
        )
    
    def get_node(self, node_id: str) -> dict | None:
        """Get node data by ID."""
        if node_id in self._graph:
            return dict(self._graph.nodes[node_id])
        return None
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges."""
        if node_id in self._graph:
            self._graph.remove_node(node_id)
            return True
        return False
    
    def has_node(self, node_id: str) -> bool:
        """Check if node exists."""
        return node_id in self._graph
    
    def get_nodes_by_type(self, node_type: NodeType) -> list[str]:
        """Get all node IDs of a specific type."""
        return [
            node_id for node_id, data in self._graph.nodes(data=True)
            if data.get("node_type") == node_type.value
        ]
    
    def update_node(self, node_id: str, **attributes) -> bool:
        """Update node attributes."""
        if node_id in self._graph:
            self._graph.nodes[node_id].update(attributes)
            return True
        return False
    
    # =========================================================================
    # EDGE OPERATIONS
    # =========================================================================
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        **attributes
    ) -> str | None:
        """
        Add an edge between two nodes.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of relationship
            **attributes: Additional edge attributes
            
        Returns:
            Edge key if successful, None if nodes don't exist
        """
        if source_id not in self._graph or target_id not in self._graph:
            return None
        
        key = self._graph.add_edge(
            source_id,
            target_id,
            edge_type=edge_type.value,
            **attributes
        )
        return key
    
    def get_edges(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | None = None
    ) -> list[dict]:
        """Get all edges between two nodes, optionally filtered by type."""
        if not self._graph.has_edge(source_id, target_id):
            return []
        
        edges = []
        for key, data in self._graph[source_id][target_id].items():
            if edge_type is None or data.get("edge_type") == edge_type.value:
                edges.append({"key": key, **data})
        return edges
    
    def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | None = None,
        key: int | None = None
    ) -> bool:
        """Remove edge(s) between nodes."""
        if not self._graph.has_edge(source_id, target_id):
            return False
        
        if key is not None:
            self._graph.remove_edge(source_id, target_id, key=key)
            return True
        
        if edge_type is not None:
            # Remove all edges of specific type
            keys_to_remove = [
                k for k, data in self._graph[source_id][target_id].items()
                if data.get("edge_type") == edge_type.value
            ]
            for k in keys_to_remove:
                self._graph.remove_edge(source_id, target_id, key=k)
            return len(keys_to_remove) > 0
        
        # Remove all edges between nodes
        self._graph.remove_edges_from([(source_id, target_id)])
        return True
    
    def get_outgoing_edges(
        self,
        node_id: str,
        edge_type: EdgeType | None = None
    ) -> list[tuple[str, dict]]:
        """Get all outgoing edges from a node."""
        if node_id not in self._graph:
            return []
        
        results = []
        for target_id in self._graph.successors(node_id):
            for key, data in self._graph[node_id][target_id].items():
                if edge_type is None or data.get("edge_type") == edge_type.value:
                    results.append((target_id, {"key": key, **data}))
        return results
    
    def get_incoming_edges(
        self,
        node_id: str,
        edge_type: EdgeType | None = None
    ) -> list[tuple[str, dict]]:
        """Get all incoming edges to a node."""
        if node_id not in self._graph:
            return []
        
        results = []
        for source_id in self._graph.predecessors(node_id):
            for key, data in self._graph[source_id][node_id].items():
                if edge_type is None or data.get("edge_type") == edge_type.value:
                    results.append((source_id, {"key": key, **data}))
        return results
    
    # =========================================================================
    # CONVENIENCE METHODS: SPATIAL
    # =========================================================================
    
    def add_level(self, level_id: str, name: str, **data) -> None:
        """Add a dungeon level/area."""
        self.add_node(level_id, NodeType.LEVEL, name=name, **data)
    
    def add_room(
        self,
        room_id: str,
        name: str,
        level_id: str | None = None,
        **data
    ) -> None:
        """Add a room, optionally within a level."""
        self.add_node(room_id, NodeType.ROOM, name=name, **data)
        if level_id and self.has_node(level_id):
            self.add_edge(level_id, room_id, EdgeType.CONTAINS)
    
    def connect_rooms(
        self,
        room1_id: str,
        room2_id: str,
        door_id: str | None = None,
        bidirectional: bool = True,
        **door_data
    ) -> None:
        """
        Connect two rooms, optionally via a door.
        
        Args:
            room1_id: First room ID
            room2_id: Second room ID
            door_id: Optional door ID (creates door node if provided)
            bidirectional: If True, connection works both ways
            **door_data: Additional door attributes
        """
        if door_id:
            self.add_node(door_id, NodeType.DOOR, **door_data)
            self.add_edge(room1_id, door_id, EdgeType.CONNECTS_TO)
            self.add_edge(door_id, room2_id, EdgeType.LEADS_TO)
            if bidirectional:
                self.add_edge(room2_id, door_id, EdgeType.CONNECTS_TO)
                self.add_edge(door_id, room1_id, EdgeType.LEADS_TO)
        else:
            self.add_edge(room1_id, room2_id, EdgeType.CONNECTS_TO)
            if bidirectional:
                self.add_edge(room2_id, room1_id, EdgeType.CONNECTS_TO)
    
    def get_connected_rooms(self, room_id: str) -> list[tuple[str, str | None]]:
        """
        Get rooms connected to given room.
        
        Returns:
            List of (room_id, door_id or None) tuples
        """
        results = []
        
        # Direct connections
        for target_id, edge_data in self.get_outgoing_edges(room_id, EdgeType.CONNECTS_TO):
            target_node = self.get_node(target_id)
            if target_node and target_node.get("node_type") == NodeType.ROOM.value:
                results.append((target_id, None))
            elif target_node and target_node.get("node_type") == NodeType.DOOR.value:
                # Follow door to next room
                for next_room_id, _ in self.get_outgoing_edges(target_id, EdgeType.LEADS_TO):
                    results.append((next_room_id, target_id))
        
        return results
    
    def get_rooms_in_level(self, level_id: str) -> list[str]:
        """Get all room IDs within a level."""
        return [
            target_id for target_id, _ 
            in self.get_outgoing_edges(level_id, EdgeType.CONTAINS)
            if self.get_node(target_id).get("node_type") == NodeType.ROOM.value
        ]
    
    # =========================================================================
    # CONVENIENCE METHODS: ENTITIES
    # =========================================================================
    
    def add_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: Literal["monster", "npc", "creature"] = "creature",
        room_id: str | None = None,
        **data
    ) -> None:
        """Add an entity, optionally placing it in a room."""
        self.add_node(entity_id, NodeType.ENTITY, name=name, entity_type=entity_type, **data)
        if room_id and self.has_node(room_id):
            self.add_edge(entity_id, room_id, EdgeType.LOCATED_IN)
    
    def move_entity(self, entity_id: str, new_room_id: str) -> bool:
        """Move an entity to a new room."""
        if not self.has_node(entity_id) or not self.has_node(new_room_id):
            return False
        
        # Remove existing location edges
        current_locations = self.get_outgoing_edges(entity_id, EdgeType.LOCATED_IN)
        for room_id, edge_data in current_locations:
            self.remove_edge(entity_id, room_id, EdgeType.LOCATED_IN)
        
        # Add new location
        self.add_edge(entity_id, new_room_id, EdgeType.LOCATED_IN)
        return True
    
    def get_entity_location(self, entity_id: str) -> str | None:
        """Get the room ID where an entity is located."""
        locations = self.get_outgoing_edges(entity_id, EdgeType.LOCATED_IN)
        return locations[0][0] if locations else None
    
    def get_entities_in_room(self, room_id: str) -> list[str]:
        """Get all entity IDs in a room."""
        return [
            source_id for source_id, _ 
            in self.get_incoming_edges(room_id, EdgeType.LOCATED_IN)
        ]
    
    # =========================================================================
    # CONVENIENCE METHODS: ITEMS
    # =========================================================================
    
    def add_item(
        self,
        item_id: str,
        name: str,
        is_macguffin: bool = False,
        room_id: str | None = None,
        owner_id: str | None = None,
        **data
    ) -> None:
        """Add an item to the world."""
        node_type = NodeType.MACGUFFIN if is_macguffin else NodeType.ITEM
        self.add_node(item_id, node_type, name=name, **data)
        
        if room_id and self.has_node(room_id):
            self.add_edge(room_id, item_id, EdgeType.CONTAINS)
        elif owner_id and self.has_node(owner_id):
            self.add_edge(owner_id, item_id, EdgeType.OWNS)
    
    def transfer_item(
        self,
        item_id: str,
        new_owner_id: str | None = None,
        new_room_id: str | None = None
    ) -> bool:
        """Transfer item ownership or location."""
        if not self.has_node(item_id):
            return False
        
        # Remove current ownership/location
        for source_id, _ in self.get_incoming_edges(item_id, EdgeType.CONTAINS):
            self.remove_edge(source_id, item_id, EdgeType.CONTAINS)
        for source_id, _ in self.get_incoming_edges(item_id, EdgeType.OWNS):
            self.remove_edge(source_id, item_id, EdgeType.OWNS)
        
        # Set new ownership/location
        if new_owner_id and self.has_node(new_owner_id):
            self.add_edge(new_owner_id, item_id, EdgeType.OWNS)
        elif new_room_id and self.has_node(new_room_id):
            self.add_edge(new_room_id, item_id, EdgeType.CONTAINS)
        
        return True
    
    # =========================================================================
    # CONVENIENCE METHODS: LORE & NARRATIVE
    # =========================================================================
    
    def add_lore(
        self,
        lore_id: str,
        name: str,
        lore_type: str,
        involved_ids: list[str] | None = None,
        **data
    ) -> None:
        """Add a piece of lore to the graph."""
        self.add_node(lore_id, NodeType.LORE, name=name, lore_type=lore_type, **data)
        
        if involved_ids:
            for involved_id in involved_ids:
                if self.has_node(involved_id):
                    self.add_edge(lore_id, involved_id, EdgeType.INVOLVES)
    
    def add_relationship(
        self,
        entity1_id: str,
        entity2_id: str,
        relationship_type: str = "knows",
        bidirectional: bool = True
    ) -> None:
        """Add a relationship between two entities."""
        self.add_edge(entity1_id, entity2_id, EdgeType.KNOWS, relationship=relationship_type)
        if bidirectional:
            self.add_edge(entity2_id, entity1_id, EdgeType.KNOWS, relationship=relationship_type)
    
    def entity_learns(self, entity_id: str, lore_id: str) -> bool:
        """Record that an entity learns about a piece of lore."""
        if not self.has_node(entity_id) or not self.has_node(lore_id):
            return False
        self.add_edge(entity_id, lore_id, EdgeType.KNOWS_ABOUT)
        return True
    
    def get_entity_knowledge(self, entity_id: str) -> list[str]:
        """Get all lore IDs that an entity knows about."""
        return [
            target_id for target_id, _ 
            in self.get_outgoing_edges(entity_id, EdgeType.KNOWS_ABOUT)
        ]
    
    def link_story_moments(self, moment1_id: str, moment2_id: str) -> None:
        """Link two story moments (moment1 triggers moment2)."""
        self.add_edge(moment1_id, moment2_id, EdgeType.TRIGGERS)
    
    # =========================================================================
    # PATH FINDING
    # =========================================================================
    
    def find_path(
        self,
        start_id: str,
        end_id: str,
        edge_types: list[EdgeType] | None = None
    ) -> list[str] | None:
        """
        Find shortest path between two nodes.
        
        Args:
            start_id: Starting node ID
            end_id: Ending node ID
            edge_types: Optional filter for edge types to traverse
            
        Returns:
            List of node IDs in path, or None if no path exists
        """
        if start_id not in self._graph or end_id not in self._graph:
            return None
        
        if edge_types:
            # Create filtered view
            def edge_filter(u, v, key, data):
                return data.get("edge_type") in [et.value for et in edge_types]
            
            view = nx.subgraph_view(
                self._graph,
                filter_edge=edge_filter
            )
            try:
                return nx.shortest_path(view, start_id, end_id)
            except nx.NetworkXNoPath:
                return None
        else:
            try:
                return nx.shortest_path(self._graph, start_id, end_id)
            except nx.NetworkXNoPath:
                return None
    
    def find_room_path(self, start_room_id: str, end_room_id: str) -> list[str] | None:
        """Find path between two rooms (via CONNECTS_TO and LEADS_TO edges)."""
        return self.find_path(
            start_room_id,
            end_room_id,
            edge_types=[EdgeType.CONNECTS_TO, EdgeType.LEADS_TO]
        )
    
    # =========================================================================
    # QUERIES
    # =========================================================================
    
    def get_subgraph(self, node_ids: list[str]) -> "WorldGraph":
        """Get a subgraph containing only specified nodes."""
        subgraph = WorldGraph()
        subgraph._graph = self._graph.subgraph(node_ids).copy()
        return subgraph
    
    def get_neighborhood(
        self,
        node_id: str,
        depth: int = 1,
        edge_types: list[EdgeType] | None = None
    ) -> list[str]:
        """Get all nodes within N edges of a node."""
        if node_id not in self._graph:
            return []
        
        visited = {node_id}
        frontier = [node_id]
        
        for _ in range(depth):
            next_frontier = []
            for current in frontier:
                # Outgoing
                for target_id, edge_data in self.get_outgoing_edges(current, None):
                    if edge_types is None or EdgeType(edge_data.get("edge_type")) in edge_types:
                        if target_id not in visited:
                            visited.add(target_id)
                            next_frontier.append(target_id)
                # Incoming
                for source_id, edge_data in self.get_incoming_edges(current, None):
                    if edge_types is None or EdgeType(edge_data.get("edge_type")) in edge_types:
                        if source_id not in visited:
                            visited.add(source_id)
                            next_frontier.append(source_id)
            frontier = next_frontier
        
        visited.discard(node_id)  # Don't include starting node
        return list(visited)
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def save_to_db(self, db) -> None:
        """Save graph to SQLite database."""
        graph_data = pickle.dumps(self._graph)
        db.execute(
            """
            INSERT OR REPLACE INTO world_graph (id, graph_data, node_count, edge_count, updated_at)
            VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (graph_data, self._graph.number_of_nodes(), self._graph.number_of_edges())
        )
        db.commit()
    
    def load_from_db(self, db) -> bool:
        """Load graph from SQLite database."""
        row = db.fetch_one("SELECT graph_data FROM world_graph WHERE id = 1")
        if row:
            self._graph = pickle.loads(row["graph_data"])
            return True
        return False
    
    def save_to_file(self, path: Path | str) -> None:
        """Save graph to a file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._graph, f)
    
    def load_from_file(self, path: Path | str) -> bool:
        """Load graph from a file."""
        path = Path(path)
        if path.exists():
            with open(path, "rb") as f:
                self._graph = pickle.load(f)
            return True
        return False
    
    def export_to_json(self) -> dict:
        """Export graph to JSON-serializable dict."""
        return nx.node_link_data(self._graph)
    
    def import_from_json(self, data: dict) -> None:
        """Import graph from JSON data."""
        self._graph = nx.node_link_graph(data, multigraph=True, directed=True)
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    @property
    def node_count(self) -> int:
        """Total number of nodes."""
        return self._graph.number_of_nodes()
    
    @property
    def edge_count(self) -> int:
        """Total number of edges."""
        return self._graph.number_of_edges()
    
    def get_stats(self) -> dict:
        """Get graph statistics."""
        type_counts = {}
        for _, data in self._graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        
        edge_type_counts = {}
        for _, _, data in self._graph.edges(data=True):
            edge_type = data.get("edge_type", "unknown")
            edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        
        return {
            "total_nodes": self.node_count,
            "total_edges": self.edge_count,
            "nodes_by_type": type_counts,
            "edges_by_type": edge_type_counts,
        }
    
    def __repr__(self) -> str:
        return f"WorldGraph(nodes={self.node_count}, edges={self.edge_count})"
