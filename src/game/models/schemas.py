from typing import List, TypedDict
from dataclasses import dataclass, field
from enum import Enum
# Enum Classes
class Attribute(str, Enum):         # Attributes (D&D standard six)
    STR = 'STR'
    DEX = 'DEX'
    CON = 'CON'
    INT = 'INT'
    WIS = 'WIS'
    CHA = 'CHA'
@dataclass
class Attributes(TypedDict):        # Set of attribute values for an entity.
    STR: int
    DEX: int
    CON: int
    INT: int
    WIS: int
    CHA: int
class Dice(str, Enum):              # Dice.
    D4 = 'd4'
    D6 = 'd6'
    D8 = 'd8'
    D10 = 'd10'
    D12 = 'd12'
    D20 = 'd20'
    D100 = 'd100'
@dataclass
class Diceset(TypedDict):          # Dict for keeping track of damage or saving throw rolls.
    D4: int
    D6: int
    D8: int
    D10: int
    D12: int
    D20: int
    D100: int
class Target(str, Enum):            # Type of targeting used by actions, attacks, and spells
    MELEE = "melee"                     # --Targeting   --Single    --Local
    RANGED = "ranged"                   # --Targeting   --Single    --Ranged
    TOUCH = "touch"                     # --Nontargeting--Single    --Local
    AOE = "aoe"                         # --Nontargeting--Multiple  --Ranged
    SELF = "self"                       # --Nontargeting--Single    --Local
class Genre(str, Enum):             # Different types of Lore we store in the DB.
    RELATIONSHIP = "relationship"
    MOTIVE = "motive"
    KNOWLEDGE = "knowledge"
    HISTORY = "history"
    CHARACTER_TRAIT = "character_trat "

# Object Classes
# Basic object model.
@dataclass
class Base:
    id: str
    name: str | None
    description: str
@dataclass
class Status(Base):
    bonuses: Attributes | None
    is_feat: bool


#  EXTRAS: -- Save for later after I work out the actual engine logic of this game
# # Lore is knowledge of the world, history or characters. Ties together different involved entities|items|locations.
# class Lore(Base):
#     genre: Genre
#     pc_knows: Requirement | bool = True
#     involved: List[str] | None
# # Magic and Enchanted Items 
# class School(str, Enum):
#     ABJURATION = 'Abjuration'
#     CONJURATION = 'Conjuration'
#     DIVINATION = 'Divination'
#     ENCHANTMENT = 'Enchantment'
#     EVOCATION = 'Evocation'
#     ILLUSION = 'Illusion'
#     NECROMANCY = 'Necromancy'
#     TRANSMUTATION = 'Transmutation'
# class SpellStats:
#     level: int
#     school: School
#     spell_slots_used: List[int] | None
#     components: List[Item] | None
#     duration: int
#     damage: Diceroll
# class Spell(Action):
#     attack_stats: AttackStats
# class MacGuffin(Item):
#     spells: List[Spell | str] | None
#     lore: List[Lore | str] | None
#     relationships: List[Character | str] | None

# Location/Environment Objects

