from src.game.models.schemas import Base, Attribute, Attributes, Status
from typing import List, Tuple
from dataclasses import dataclass

# Simple Item and Weapon classes
@dataclass
class AttackStats:
    range: int
    base_attribute: Attribute
    damage: str

@dataclass
class Item(Base):
    hp: Tuple[str,str]
    cost: int
    weight: int
    effects: List[Status] | None
    attack_stats: AttackStats | None

# # Conversation History classes for PC and NPC conversations
# class Message:
#     text: str
#     speaker_id: str
#     listener_id: str
# class Conversation:
#     id: str
#     messages: List[Message]
# class ConversationSummary(Base):
#     pass

# PC Stats 
@dataclass
class PlayerCharacter:
    # Static Stats
    _class: str
    level: int
    attributes: Attributes
    max_hp: int
    ac: int
    capacity: int
    feats: List[Status]
    # spells: List[Lore | str] | None
    # Semi-Dynamic Stats (Status + Roleplay)
    # knowledge: List[Lore | str] | None
    # memories: List[Lore | str] | None
    # prior_conversations: List[Conversation | ConversationSummary] | None
    # Inventory and Experience
    xp: Tuple [int,int]
    gold: int
    inventory: List[Item]
    # Dynamic Stats (Combat)
    equipped: List[Item]
    spell_slots: List[int] | None
    # to_notice: Requirement | None
    conditions: List[Status] | None
    hp: int
# NPCs and Monsters
@dataclass
class Entity(Base):
    xp: int | None
    attributes: Attributes
    max_hp: int
    max_morale: int
    ac: int
@dataclass
class Grunt(Entity):
    hp: int
    morale: int
    conditions: List[Status | str] | None
    inventory: List[Item | str] | None
    equipped: List[Item | str] | None
    # to_notice: Requirement | None
# class Character(Grunt):
#     disposition: str
#     prior_conversations: List[Conversation | ConversationSummary] | None
#     feats: List[Feat | str] | None
#     # lore: List[Lore | str] | None

# Locations
@dataclass
class Location(Base):
    # possibilities: List[Lore] | None
    is_explored: bool
# class Door(Location):
#     next_room_id: str                       # ID of connecting room.
#     is_open: bool
#     locked: Requirement | None
#     to_notice: Requirement | None
@dataclass
class Room(Location):
    # doors: List[Door | str] | None
    occupants: List[Entity | str] | None
    items: List[Item | str] | None
@dataclass
class Level(Base):
    room_ids: List[str]
    # hooks: List[Lore] | None
    effects: List[Status] | None

# class Trap(Base):
#     to_notice: Requirement | None      # Anything to_notice must have Requirement met to be seen
#     to_trigger: Requirement | None     # Trap must have requirement met to be triggered.
#     attack_stats: AttackStats

@dataclass
class CombatantStatus:
    entity: Entity
    friendly: bool


@dataclass
class Combat:
    current_active_entity: str
    combatants: List[CombatantStatus]

@dataclass
class GameState:
    """Aggregate root - the 'current situation' snapshot"""
    # Meta
    # session_id: str
    # created_at: datetime
    # updated_at: datetime
    
    # Player
    player: PlayerCharacter
    
    # Current context (what's immediately relevant)
    current_level: Level
    current_room: Room
    
    # Active interactions
    # active_combat: Combat | None
    # active_conversation: Conversation | None
    
    # Recent history (for context)
    recent_actions: list[str]  # last 5-10 actions