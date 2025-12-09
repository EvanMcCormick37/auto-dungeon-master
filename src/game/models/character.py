from typing import Tuple, List
from src.game.models.base import Base, Attributes, Feat, Status, Action, Attack, Item, Lore, Requirement
from src.game.models.spell import Spell


# Conversation History classes for PC and NPC conversations
class Message:
    text: str
    speaker_id: str
    listener_id: str
class Conversation:
    id: str
    messages: List[Message]
class ConversationSummary(Base):
    pass


# PC Stats 
class PlayerCharacter:
    # Static Stats
    _class: str
    level: int
    attributes: Attributes
    max_hp: int
    ac: int
    capacity: int
    feats: List[Feat]
    spells: List[Lore | str] | None
    # Semi-Dynamic Stats (Status + Roleplay)
    knowledge: List[Lore | str] | None
    memories: List[Lore | str] | None
    prior_conversations: List[Conversation | ConversationSummary] | None
    # Inventory and Experience
    experience: Tuple [int,int]
    gold: int
    inventory: List[Item]
    # Dynamic Stats (Combat)
    equipped: List[Item]
    spell_slots: List[int] | None
    hidden: Requirement | bool = False
    conditions: List[Status] | None
    hp: int


# NPCs and Monsters
class Entity(Base):
    xp: int | None
    attributes: Attributes
    max_hp: int
    max_morale: int
    ac: int
    actions: List[Action | str] | None
    attacks: List[Attack | str] | None
# Instantiated Entities, generic enemies with no lore or character attached.
class Grunt(Base):
    hp: int
    morale: int
    conditions: List[Status | str] | None
    inventory: List[Item | str] | None
    equipped: List[Item | str] | None
    hidden: Requirement | bool = False
# RP properties for NPCs and singleton monsters with Lore
class Character(Grunt):
    disposition: str
    prior_conversations: List[Conversation | ConversationSummary] | None
    feats: List[Feat | str] | None
    lore: List[Lore | str] | None