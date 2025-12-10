# src/game/core/state_manager.py

import logging
from typing import Any, List
from src.game.models import GameState, PlayerCharacter, Entity, Item, Room, StateChange

logger = logging.getLogger(__name__)

class StateManager:
    """
    Central controller for accessing and mutating the GameState.
    Ensures all state changes are centralized, logged, and valid.
    """
    def __init__(self, initial_state: GameState):
        self._state = initial_state

    def get_current_state(self) -> GameState:
        """Return the current snapshot of the game state."""
        return self._state

    def get_entity(self, entity_id: str) -> Entity | PlayerCharacter | Item | Room | None:
        """
        Searches the GameState hierarchy to find an object by its ID.
        
        Search Order:
        1. Player
        2. Player Inventory
        3. Current Room (Location)
        4. Room Occupants (NPCs/Monsters)
        5. Room Items
        """
        state = self._state

        # 1. Check Player
        if state.player.id == entity_id:
            return state.player
        
        # 2. Check Player Inventory
        for item in state.player.inventory:
            if item.id == entity_id:
                return item

        # 3. Check Location (Room)
        if state.location.id == entity_id:
            return state.location

        # 4. Check Room Occupants
        if state.location.occupants:
            for entity in state.location.occupants:
                if isinstance(entity, str): continue # Skip if just ID reference
                if entity.id == entity_id:
                    return entity
                # 4b. Check Entity Inventory (if needed)
                # (Optional: Add recursion here if NPCs have accessible inventories)

        # 5. Check Room Items
        if state.location.items:
            for item in state.location.items:
                if isinstance(item, str): continue
                if item.id == entity_id:
                    return item

        return None
    
    def get_alive_enemies_in_room(self) -> List[Entity]:
        """
        Returns a list of the living entities in the current room (hp > 0).
        Assumes all Entities in the room are enemies.
        """
        room = self._state.location
        alive_enemies = []

        if not room.occupants:
            return alive_enemies

        for entity in room.occupants:
            if entity.hp > 0:
                alive_enemies.append(entity)

        return alive_enemies

    def apply_change(self, change: StateChange) -> None:
        """
        Executes a specific StateChange on the game state.
        
        Handles:
        - Nested attributes (e.g. "attributes.STR")
        - Numeric operations (add/remove)
        - List operations (append/remove)
        - Direct sets
        """
        target = self.get_entity(change.target_id)
        
        if not target:
            logger.error(f"Failed to apply state change: Target {change.target_id} not found.")
            return

        try:
            self._mutate_target(target, change)
            logger.info(f"State applied: {change.target_id}.{change.attribute} {change.operation} {change.value}")
        except Exception as e:
            logger.error(f"Error applying state change to {change.target_id}: {str(e)}")
            raise e

    def _mutate_target(self, target: Any, change: StateChange) -> None:
        """Internal helper to perform the mutation logic."""
        
        # 1. Resolve the attribute path (e.g., "attributes.STR" -> target.attributes["STR"])
        # We need to get the *parent* object and the *key* to set the final value.
        attr_path = change.attribute.split('.')
        parent = target
        
        # Traverse down to the second-to-last element
        for key in attr_path[:-1]:
            if isinstance(parent, dict):
                parent = parent.get(key)
            else:
                parent = getattr(parent, key)
                
            if parent is None:
                raise AttributeError(f"Path '{change.attribute}' broken at '{key}' on {target}")

        final_key = attr_path[-1]

        # 2. Get the current value
        if isinstance(parent, dict):
            current_value = parent.get(final_key)
        else:
            current_value = getattr(parent, final_key)

        # 3. Perform Operation
        new_value = current_value

        match change.operation:
            case "set":
                new_value = change.value
            
            case "add":
                # Numeric addition
                if isinstance(current_value, (int, float)):
                    new_value = current_value + change.value
                else:
                    raise ValueError(f"Cannot 'add' to non-numeric type {type(current_value)}")
            
            case "remove":
                # Numeric subtraction OR List removal
                if isinstance(current_value, (int, float)):
                    new_value = current_value - change.value
                elif isinstance(current_value, list):
                    # For lists, we modify in place, but let's be safe
                    if change.value in current_value:
                        current_value.remove(change.value)
                    new_value = current_value
                else:
                    raise ValueError(f"Cannot 'remove' from type {type(current_value)}")

            case "append":
                if isinstance(current_value, list):
                    current_value.append(change.value)
                    new_value = current_value
                else:
                     raise ValueError(f"Cannot 'append' to non-list type {type(current_value)}")
            
            case _:
                raise ValueError(f"Unknown operation: {change.operation}")

        # 4. Commit Change
        if isinstance(parent, dict):
            parent[final_key] = new_value
        else:
            setattr(parent, final_key, new_value)