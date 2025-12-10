from uuid import uuid4
from typing import List

from src.game.core.resolution_engine import ResolutionEngine
from src.game.core.action_queue import ActionQueue
from src.game.core.state_manager import StateManager
from src.game.models import Action, Resolution
from src.game.llm import NarratorOracle, GMOracle


class GameController:
    """
    Main game loop coordinator.
    Orchestrates player actions, enemy turns, and combat flow.
    """
    
    def __init__(
        self,
        gm_oracle: GMOracle,
        resolution_engine: ResolutionEngine,
        state_manager: StateManager,
        narrator_oracle: NarratorOracle
    ):
        self.gm = gm_oracle
        self.engine = resolution_engine
        self.state = state_manager
        self.narrator = narrator_oracle
        self.action_queue = ActionQueue()
        self.narration_buffer: List[str] = []
        self.turn_based = False
    
    def process_player_input(self, text: str) -> str:
        """Main entry point for player commands."""
        self.narration_buffer.clear()
        
        # 1. Process Player
        self._enqueue_action(owner_id="player", text=text)
        self._process_queue()
        
        # 2. Check & Handle Combat
        self.turn_based = self.state.has_hostile_entities_in_room()
        
        if self.turn_based:
            self._process_enemy_turns()
            
            if result := self._check_combat_result():
                self.narration_buffer.append(result)
                self.turn_based = False
        # 3. Finalize Output
        narration = self.narrator.compose_narration(
            self.narration_buffer,
            self.state.get_current_state()
        )
        # Check for end of combat.
        combat_result = self._check_combat_result()
        return f"{narration}{combat_result}"
    
    def _enqueue_action(self, owner_id: str, text: str, priority: int = 0) -> None:
        """Helper to create and queue an Action object."""
        action = Action(
            id=f"action_{uuid4().hex[:8]}",
            owner_id=owner_id,
            intent_text=text,
            priority=priority
        )
        self.action_queue.enqueue(action)

    def _process_enemy_turns(self) -> None:
        """Process actions for all alive enemies."""
        for enemy in self.state.get_alive_enemies_in_room():
            if not self._is_player_alive():
                break
            
            intent = self.gm.generate_enemy_action(enemy, self.state.get_current_state())
            if intent:
                self._enqueue_action(owner_id=enemy.id, text=intent)
                self._process_queue()

    def _process_queue(self) -> None:
        """Process actions until queue is empty or safety limit reached."""
        iterations = 0
        max_iterations = 50 
        
        while not self.action_queue.is_empty():
            if iterations >= max_iterations:
                self.narration_buffer.append("[The chaos becomes too complex to follow...]")
                break

            self._resolve_action(self.action_queue.dequeue())
            iterations += 1

    def _resolve_action(self, action: Action) -> None:
        """Execute the Intent -> Plan -> Execute -> State pipeline for a single action."""
        try:
            # Phase 1: INTERPRET (LLM)
            context = self.state.get_relevant_context(action)
            action.plan = self.gm.interpret_action(action.intent_text, context)
            
            if action.plan is None:
                self.narration_buffer.append(self.gm.explain_invalid_action(action.intent_text, context))
                return

            # Phase 2: EXECUTE (Engine)
            action.resolution = Resolution(action_plan=action.plan)
            action.resolution = self.engine.execute_plan(action.resolution)
            
            if action.resolution.narration_fragments:
                self.narration_buffer.extend(action.resolution.narration_fragments)
            
            # Phase 3: APPLY STATE
            for change in action.resolution.pending_state_changes:
                self.state.apply_change(change)
            
            # Phase 4: REACT
            for reaction in action.resolution.triggered_reactions:
                desc = self.gm.describe_reaction(
                    reaction.owner_id, action, self.state.get_entity(reaction.owner_id)
                )
                # Queue reactions as new actions
                # Note: Reaction objects usually have their own method to convert to Action, 
                # but following your logic we treat them as intents here.
                reaction.intent_text = desc 
                self.action_queue.enqueue_reaction(reaction)

        except Exception as e:
            self.narration_buffer.append(f"[An error occurred processing action: {str(e)}]")

    def _check_combat_result(self) -> str | None:
        """Return narration if combat resolved, otherwise None."""
        if not self._is_player_alive():
            return "\n[DEFEAT: You have fallen unconscious. Game Over.]"
        
        if not self.state.has_hostile_entities_in_room():
            return "\n[VICTORY: All enemies have been defeated!]"
        
        return None
    
    def _is_player_alive(self) -> bool:
        player = self.state.get_player_character()
        return player.hp > 0 if player else False