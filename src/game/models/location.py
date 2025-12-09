from typing import List
from src.game.models.base import Base, Item, Lore, Status, AttackStats, Requirement
from src.game.models.character import Entity
class Trap(Base):
    hidden: Requirement | bool = False      # Anything hidden must have Requirement met to be seen
    trigger: Requirement | bool = False     # Trap must have requirement met to be triggered.
    attack_stats: AttackStats

class Location(Base):
    explored: bool
    traps: List[Trap] | None
    possibilities: List[Lore] | None
    is_explored: bool

class Door(Location):
    next_room_id: str                       # ID of connecting room.
    is_open: bool
    locked: Requirement | bool = False
    hidden: Requirement | bool = False
    trap: Trap | None

class Room(Location):
    doors: List[Door | str] | None
    occupants: List[Entity | str] | None
    items: List[Item | str] | None

class Level(Base):
    room_ids: List[str]
    hooks: List[Lore] | None
    effects: List[Status] | None