#!/usr/bin/env python3
"""
Test script to verify the storage layer schemas work correctly.
Run with: python test_storage.py
"""

import tempfile
from pathlib import Path


def test_sqlite_database():
    """Test SQLite schema initialization and basic operations."""
    print("\n=== Testing SQLite Database ===")
    
    from storage.database import Database, to_json, from_json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        
        # Initialize schema
        db.init_schema()
        print(f"✓ Schema initialized (version {db.get_schema_version()})")
        
        # Check tables exist
        expected_tables = [
            "lore", "statuses", "actions", "attacks", "feats",
            "items", "spells", "entities", "traps", "rooms",
            "doors", "levels", "conversations", "requirements",
            "saved_games", "world_graph"
        ]
        
        for table in expected_tables:
            assert db.table_exists(table), f"Missing table: {table}"
        print(f"✓ All {len(expected_tables)} tables created")
        
        # Test insert/query
        db.execute(
            """
            INSERT INTO items (id, name, description, item_type, cost, weight)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sword_001", "Longsword", "A versatile martial weapon", "weapon", 15, 3)
        )
        db.commit()
        
        row = db.fetch_one("SELECT * FROM items WHERE id = ?", ("sword_001",))
        assert row["name"] == "Longsword"
        print("✓ Insert/query operations work")
        
        # Test JSON helpers
        test_dict = {"STR": 10, "DEX": 14}
        json_str = to_json(test_dict)
        restored = from_json(json_str)
        assert restored == test_dict
        print("✓ JSON serialization helpers work")
        
        db.close()
        print("✓ SQLite tests passed!")


def test_world_graph():
    """Test NetworkX world graph operations."""
    print("\n=== Testing WorldGraph ===")
    
    from storage.graph import WorldGraph, NodeType, EdgeType
    
    graph = WorldGraph()
    
    # Add a level with rooms
    graph.add_level("dungeon_l1", "Dungeon Level 1")
    graph.add_room("room_entrance", "Entrance Hall", level_id="dungeon_l1")
    graph.add_room("room_corridor", "Dark Corridor", level_id="dungeon_l1")
    graph.add_room("room_treasure", "Treasure Room", level_id="dungeon_l1")
    
    print(f"✓ Added level with {len(graph.get_rooms_in_level('dungeon_l1'))} rooms")
    
    # Connect rooms
    graph.connect_rooms("room_entrance", "room_corridor", door_id="door_01", name="Wooden Door")
    graph.connect_rooms("room_corridor", "room_treasure", door_id="door_02", name="Iron Gate", is_locked=True)
    
    connected = graph.get_connected_rooms("room_entrance")
    assert len(connected) == 1
    assert connected[0][0] == "room_corridor"
    print("✓ Room connections work")
    
    # Add entities
    graph.add_entity("goblin_01", "Sneaky Goblin", entity_type="monster", room_id="room_corridor")
    graph.add_entity("merchant_01", "Old Merchant", entity_type="npc", room_id="room_entrance")
    
    entities_in_corridor = graph.get_entities_in_room("room_corridor")
    assert "goblin_01" in entities_in_corridor
    print("✓ Entity placement works")
    
    # Move entity
    graph.move_entity("goblin_01", "room_treasure")
    new_location = graph.get_entity_location("goblin_01")
    assert new_location == "room_treasure"
    print("✓ Entity movement works")
    
    # Add lore
    graph.add_lore(
        "lore_secret", 
        "Hidden Treasure Location",
        lore_type="secret",
        involved_ids=["room_treasure", "merchant_01"]
    )
    graph.entity_learns("merchant_01", "lore_secret")
    
    knowledge = graph.get_entity_knowledge("merchant_01")
    assert "lore_secret" in knowledge
    print("✓ Lore and knowledge tracking works")
    
    # Path finding
    path = graph.find_room_path("room_entrance", "room_treasure")
    assert path is not None
    print(f"✓ Path finding works: {' -> '.join(path)}")
    
    # Stats
    stats = graph.get_stats()
    print(f"✓ Graph stats: {stats['total_nodes']} nodes, {stats['total_edges']} edges")
    
    # Test serialization
    json_data = graph.export_to_json()
    new_graph = WorldGraph()
    new_graph.import_from_json(json_data)
    assert new_graph.node_count == graph.node_count
    print("✓ JSON serialization works")
    
    print("✓ WorldGraph tests passed!")


def test_vector_store():
    """Test LanceDB vector store operations."""
    print("\n=== Testing VectorStore ===")
    
    from storage.vectors import (
        VectorStore, VectorCollection, 
        RulesDocument, LoreDocument, EntityDocument
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(db_path=Path(tmpdir) / "vectors")
        
        # Create collections
        store.create_all_collections()
        collections = store.list_collections()
        print(f"✓ Created {len(collections)} collections")
        
        # Add rules documents
        rules = [
            RulesDocument(
                id="rule_grapple",
                text="When you want to grab a creature or wrestle with it, you can use the Attack action to make a special melee attack, a grapple.",
                category="combat",
                subcategory="grappling",
                keywords=["grapple", "grab", "wrestling", "melee"]
            ),
            RulesDocument(
                id="rule_sneak_attack",
                text="Once per turn, you can deal extra 1d6 damage to one creature you hit with an attack if you have advantage on the attack roll.",
                category="combat",
                subcategory="class_features",
                keywords=["sneak attack", "rogue", "damage", "advantage"]
            ),
        ]
        store.add(VectorCollection.RULES, rules)
        print(f"✓ Added {len(rules)} rules documents")
        
        # Add lore
        lore = LoreDocument(
            id="lore_dragon_war",
            text="The Dragon Wars ravaged the northern kingdoms for three centuries, leaving only ruins and legends in their wake.",
            lore_type="history",
            region="northern_kingdoms",
            keywords=["dragon", "war", "history", "northern"]
        )
        store.add(VectorCollection.LORE, lore)
        print("✓ Added lore document")
        
        # Add entity
        entity = EntityDocument(
            id="entity_goblin",
            text="Goblin: A small, black-hearted humanoid that dwells in caves and ruins. Known for their cunning ambushes.",
            entity_type="monster",
            challenge_rating=0.25,
            creature_type="humanoid",
            keywords=["goblin", "humanoid", "cave", "ambush"]
        )
        store.add(VectorCollection.ENTITIES, entity)
        print("✓ Added entity document")
        
        # Test search
        results = store.search_rules("how do I grab an enemy", k=2)
        assert len(results) > 0
        assert "grapple" in results[0].text.lower()
        print(f"✓ Semantic search works (top result score: {results[0].score:.3f})")
        
        # Test filtered search
        combat_results = store.search_rules("damage", category="combat", k=5)
        for r in combat_results:
            assert r.metadata.get("category") == "combat"
        print("✓ Filtered search works")
        
        # Test get by ID
        doc = store.get(VectorCollection.RULES, "rule_grapple")
        assert doc is not None
        assert doc["id"] == "rule_grapple"
        print("✓ Get by ID works")
        
        # Stats
        stats = store.get_stats()
        print(f"✓ Vector store stats: {stats}")
        
        print("✓ VectorStore tests passed!")


def main():
    """Run all storage tests."""
    print("=" * 60)
    print("Storage Layer Verification Tests")
    print("=" * 60)
    
    try:
        test_sqlite_database()
        test_world_graph()
        test_vector_store()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("Make sure you have installed dependencies:")
        print("  pip install networkx lancedb sentence-transformers pyarrow")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
