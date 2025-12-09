"""
SQLite Database Connection Manager and Schema
Handles persistent storage for entities, items, spells, locations, and game saves.
"""

import sqlite3
import json
from pathlib import Path
from typing import Any, Self
from contextlib import contextmanager

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- =============================================================================
-- SCHEMA VERSION TRACKING
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- LORE TABLE
-- Knowledge of world, history, characters. Core to RAG and narrative.
-- =============================================================================
CREATE TABLE IF NOT EXISTS lore (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN (
        'possibility', 'relationship', 'motive', 
        'trait', 'location', 'secret', 'story'
    )),
    pc_knows INTEGER DEFAULT 0,  -- boolean
    involved TEXT,  -- JSON array of entity IDs
    data JSON,  -- full serialized object for extension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lore_type ON lore(type);
CREATE INDEX IF NOT EXISTS idx_lore_pc_knows ON lore(pc_knows);

-- =============================================================================
-- STATUSES TABLE
-- Temporary or permanent status effects / conditions
-- =============================================================================
CREATE TABLE IF NOT EXISTS statuses (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    bonuses JSON,  -- Attributes dict: {STR: int, DEX: int, ...}
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- ACTIONS TABLE
-- Possible actions (non-attack)
-- =============================================================================
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    type TEXT CHECK (type IN ('melee', 'ranged', 'effect', 'aoe', 'self')),
    base_attribute TEXT CHECK (base_attribute IN ('STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA')),
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_actions_type ON actions(type);

-- =============================================================================
-- ATTACKS TABLE
-- Attack actions with damage, saves, etc.
-- =============================================================================
CREATE TABLE IF NOT EXISTS attacks (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    type TEXT CHECK (type IN ('melee', 'ranged', 'effect', 'aoe', 'self')),
    base_attribute TEXT CHECK (base_attribute IN ('STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA')),
    -- AttackStats fields
    damage JSON,  -- Diceroll dict
    attack_bonus INTEGER,
    save_dc INTEGER,
    save_type TEXT CHECK (save_type IN ('STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA')),
    on_fail_status_id TEXT REFERENCES statuses(id),
    on_success_status_id TEXT REFERENCES statuses(id),
    on_hit_status_id TEXT REFERENCES statuses(id),
    on_crit_status_id TEXT REFERENCES statuses(id),
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- FEATS TABLE
-- Powers or abilities that grant statuses and/or actions
-- =============================================================================
CREATE TABLE IF NOT EXISTS feats (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    status_id TEXT REFERENCES statuses(id),
    action_ids JSON,  -- Array of action IDs
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- ITEMS TABLE
-- All items including weapons
-- =============================================================================
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'item' CHECK (item_type IN (
        'item', 'weapon', 'armor', 'consumable', 'macguffin'
    )),
    hp_current TEXT,  -- Tuple stored as "current,max"
    hp_max TEXT,
    cost INTEGER DEFAULT 0,
    weight INTEGER DEFAULT 0,
    uses JSON,  -- Array of Action IDs
    effects JSON,  -- Array of Status IDs
    hidden JSON,  -- Optional requirement object
    -- Weapon-specific fields (NULL for non-weapons)
    base_attribute TEXT CHECK (base_attribute IN ('STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA')),
    damage_roll JSON,  -- Diceroll dict
    -- MacGuffin-specific fields
    spell_ids JSON,  -- Array of spell IDs
    lore_ids JSON,  -- Array of lore IDs
    relationship_ids JSON,  -- Array of character IDs
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_items_type ON items(item_type);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);

-- =============================================================================
-- SPELLS TABLE
-- Magical actions with spell-specific stats
-- =============================================================================
CREATE TABLE IF NOT EXISTS spells (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    type TEXT CHECK (type IN ('melee', 'ranged', 'effect', 'aoe', 'self')),
    base_attribute TEXT CHECK (base_attribute IN ('STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA')),
    -- SpellStats fields
    level INTEGER NOT NULL DEFAULT 0,
    school TEXT CHECK (school IN (
        'Abjuration', 'Conjuration', 'Divination', 'Enchantment',
        'Evocation', 'Illusion', 'Necromancy', 'Transmutation'
    )),
    spell_slots_used JSON,  -- Array of ints
    component_ids JSON,  -- Array of Item IDs (material components)
    duration INTEGER,  -- in rounds/minutes
    damage JSON,  -- Diceroll dict
    -- AttackStats fields
    attack_bonus INTEGER,
    save_dc INTEGER,
    save_type TEXT CHECK (save_type IN ('STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA')),
    on_fail_status_id TEXT REFERENCES statuses(id),
    on_success_status_id TEXT REFERENCES statuses(id),
    on_hit_status_id TEXT REFERENCES statuses(id),
    on_crit_status_id TEXT REFERENCES statuses(id),
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_spells_level ON spells(level);
CREATE INDEX IF NOT EXISTS idx_spells_school ON spells(school);

-- =============================================================================
-- ENTITIES TABLE
-- Monsters, NPCs, and other creatures with stats
-- =============================================================================
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('monster', 'npc', 'creature')),
    -- Core stats
    attributes JSON NOT NULL,  -- Attributes dict
    max_hp INTEGER NOT NULL,
    max_morale INTEGER DEFAULT 100,
    ac INTEGER NOT NULL,
    -- Abilities (arrays of IDs or embedded objects)
    action_ids JSON,
    attack_ids JSON,
    feat_ids JSON,
    lore_ids JSON,
    -- Dynamic stats
    hp INTEGER,
    morale INTEGER,
    condition_ids JSON,
    inventory_ids JSON,
    equipped_ids JSON,
    hidden JSON,  -- Optional requirement
    -- Monster-specific
    xp INTEGER,
    -- NPC/Character-specific
    disposition TEXT,
    prior_conversation_ids JSON,
    data JSON,  -- Full serialized object for any extras
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);

-- =============================================================================
-- TRAPS TABLE
-- Hidden dangers in locations
-- =============================================================================
CREATE TABLE IF NOT EXISTS traps (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    hidden JSON,  -- Requirement
    trigger JSON,  -- Requirement
    -- AttackStats
    damage JSON,
    attack_bonus INTEGER,
    save_dc INTEGER,
    save_type TEXT,
    on_fail_status_id TEXT REFERENCES statuses(id),
    on_success_status_id TEXT REFERENCES statuses(id),
    on_hit_status_id TEXT REFERENCES statuses(id),
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- ROOMS TABLE
-- Individual rooms within locations
-- =============================================================================
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    level_id TEXT REFERENCES levels(id),
    explored INTEGER DEFAULT 0,
    is_explored INTEGER DEFAULT 0,
    trap_ids JSON,  -- Array of trap IDs
    possibility_ids JSON,  -- Array of Lore IDs (type=possibility)
    door_ids JSON,  -- Array of door IDs
    occupant_ids JSON,  -- Array of Entity IDs
    item_ids JSON,  -- Array of Item IDs
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- DOORS TABLE
-- Connections between rooms
-- =============================================================================
CREATE TABLE IF NOT EXISTS doors (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    from_room_id TEXT NOT NULL REFERENCES rooms(id),
    next_room_id TEXT NOT NULL REFERENCES rooms(id),
    explored INTEGER DEFAULT 0,
    is_explored INTEGER DEFAULT 0,
    is_open INTEGER DEFAULT 0,
    locked JSON,  -- Requirement or boolean
    hidden JSON,  -- Requirement or boolean
    trap_id TEXT REFERENCES traps(id),
    possibility_ids JSON,
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_doors_from_room ON doors(from_room_id);
CREATE INDEX IF NOT EXISTS idx_doors_next_room ON doors(next_room_id);

-- =============================================================================
-- LEVELS TABLE
-- Dungeon floors / areas containing rooms
-- =============================================================================
CREATE TABLE IF NOT EXISTS levels (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    room_ids JSON,  -- Array of room IDs
    hook_ids JSON,  -- Array of Lore IDs
    effect_ids JSON,  -- Array of Status IDs (environmental effects)
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- CONVERSATIONS TABLE
-- Dialogue history between PC and NPCs
-- =============================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    participant_ids JSON NOT NULL,  -- Array of entity IDs
    messages JSON NOT NULL,  -- Array of Message objects
    summary TEXT,  -- ConversationSummary if condensed
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- REQUIREMENTS TABLE
-- Conditions that must be met for something to occur
-- =============================================================================
CREATE TABLE IF NOT EXISTS requirements (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT NOT NULL,
    involved_ids JSON,  -- Array of entity/item IDs
    check JSON, -- Dict (Attribute, int) Skill checks to meet the requirement.
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SAVED GAMES TABLE
-- Serialized GameState snapshots
-- =============================================================================
CREATE TABLE IF NOT EXISTS saved_games (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    player_name TEXT,
    player_class TEXT,
    player_level INTEGER,
    current_room_id TEXT,
    current_level_id TEXT,
    state JSON NOT NULL,  -- Full serialized GameState
    playtime_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_saves_name ON saved_games(name);
CREATE INDEX IF NOT EXISTS idx_saves_updated ON saved_games(updated_at DESC);

-- =============================================================================
-- WORLD GRAPH PERSISTENCE
-- Serialized NetworkX graph for relationship queries
-- =============================================================================
CREATE TABLE IF NOT EXISTS world_graph (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Singleton row
    graph_data BLOB NOT NULL,  -- Pickled NetworkX graph
    node_count INTEGER,
    edge_count INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- TRIGGERS FOR AUTO-UPDATING TIMESTAMPS
-- =============================================================================
CREATE TRIGGER IF NOT EXISTS update_lore_timestamp 
    AFTER UPDATE ON lore
    BEGIN
        UPDATE lore SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_items_timestamp 
    AFTER UPDATE ON items
    BEGIN
        UPDATE items SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_entities_timestamp 
    AFTER UPDATE ON entities
    BEGIN
        UPDATE entities SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_rooms_timestamp 
    AFTER UPDATE ON rooms
    BEGIN
        UPDATE rooms SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_levels_timestamp 
    AFTER UPDATE ON levels
    BEGIN
        UPDATE levels SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_conversations_timestamp 
    AFTER UPDATE ON conversations
    BEGIN
        UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_saved_games_timestamp 
    AFTER UPDATE ON saved_games
    BEGIN
        UPDATE saved_games SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
"""


class Database:
    """SQLite database connection manager with schema initialization."""
    
    def __init__(self, db_path: Path | str | None = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. 
                     Use ":memory:" for in-memory database.
                     None defaults to data/game.db
        """
        if db_path is None:
            db_path = Path("data") / "game.db"
        
        self.db_path = Path(db_path) if db_path != ":memory:" else db_path
        self._connection: sqlite3.Connection | None = None
        
        # Ensure data directory exists
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")
            # Return dicts instead of tuples
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def __enter__(self) -> Self:
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single query."""
        return self.connection.execute(query, params)
    
    def executemany(self, query: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets."""
        return self.connection.executemany(query, params_list)
    
    def executescript(self, script: str) -> sqlite3.Cursor:
        """Execute multiple SQL statements."""
        return self.connection.executescript(script)
    
    def commit(self) -> None:
        """Commit the current transaction."""
        self.connection.commit()
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.connection.rollback()
    
    def fetch_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute query and fetch one result."""
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute query and fetch all results."""
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    @contextmanager
    def transaction(self):
        """Context manager for transactions with auto-commit/rollback."""
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise
    
    def init_schema(self) -> None:
        """Initialize database schema."""
        self.executescript(SCHEMA_SQL)
        
        # Record schema version
        self.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,)
        )
        self.commit()
        
    def get_schema_version(self) -> int | None:
        """Get current schema version."""
        try:
            row = self.fetch_one("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            return row["version"] if row else None
        except sqlite3.OperationalError:
            return None
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        row = self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return row is not None
    
    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table."""
        row = self.fetch_one(f"SELECT COUNT(*) as count FROM {table_name}")
        return row["count"] if row else 0


# Helper functions for JSON serialization
def to_json(obj: Any) -> str | None:
    """Serialize object to JSON string for storage."""
    if obj is None:
        return None
    return json.dumps(obj, default=str)


def from_json(json_str: str | None) -> Any:
    """Deserialize JSON string from storage."""
    if json_str is None:
        return None
    return json.loads(json_str)
