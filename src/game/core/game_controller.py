class GameController:
    """
    Main game loop coordinator.
    Manages the flow: Intent → Plan → Execute → Narrate → State Update
    """
    
    def __init__(
        self,
        dm_oracle: 'DMOracle',           # LLM interface for interpretation
        resolution_engine: ResolutionEngine,
        state_manager: 'StateManager',
        narrator: 'Narrator'              # LLM interface for prose generation
    ):
        self.dm = dm_oracle
        self.engine = resolution_engine
        self.state = state_manager
        self.narrator = narrator
        self.action_queue = ActionQueue()
        self.narration_buffer: List[str] = []
    
    def process_player_input(self, command_type: str, text: str) -> str:
        """
        Main entry point for player commands.
        Returns the full narration of what happened.
        """
        # 1. Parse into Intent
        intent = Intent(
            owner_id="player",
            command_type=command_type,  # "try", "say", "askdm"
            text=text
        )
        
        # 2. Create Action and queue it
        action = Action(
            id=f"action_{uuid4().hex[:8]}",
            owner_id="player",
            intent_text=text,
            priority=0
        )
        self.action_queue.enqueue(action)
        
        # 3. Process all queued actions (including reactions)
        self._process_queue()
        
        # 4. Generate final narration
        final_narration = self.narrator.compose_narration(
            self.narration_buffer,
            self.state.get_current_state()
        )
        
        # 5. Clear buffer and return
        self.narration_buffer.clear()
        return final_narration
    
    def _process_queue(self):
        """Process all actions in queue until empty"""
        max_iterations = 50  # Safety limit
        iterations = 0
        
        while not self.action_queue.is_empty() and iterations < max_iterations:
            iterations += 1
            action = self.action_queue.dequeue()
            
            # Phase 1: INTERPRET (LLM)
            # DM interprets the intent and creates an ActionPlan
            relevant_state = self.state.get_relevant_context(action)
            action.plan = self.dm.interpret_action(action.intent_text, relevant_state)
            
            # Handle invalid/impossible actions
            if action.plan is None:
                self.narration_buffer.append(
                    self.dm.explain_invalid_action(action.intent_text, relevant_state)
                )
                continue
            
            # Phase 2: EXECUTE (Engine)
            # Mechanical resolution—no LLM here
            action.resolution = Resolution(action_plan=action.plan)
            action.resolution = self.engine.execute_plan(action.resolution)
            
            # Collect narration fragments from rolls
            self.narration_buffer.extend(action.resolution.narration_fragments)
            
            # Phase 3: APPLY STATE CHANGES
            for change in action.resolution.pending_state_changes:
                self.state.apply_change(change)
            
            # Phase 4: QUEUE REACTIONS
            # These will be processed in subsequent iterations
            for reaction in action.resolution.triggered_reactions:
                # Get DM to flesh out the reaction intent
                reaction.intent_text = self.dm.describe_reaction(
                    reaction.owner_id,
                    action,
                    self.state.get_entity(reaction.owner_id)
                )
                self.action_queue.enqueue_reaction(reaction)
        
        if iterations >= max_iterations:
            # Safety: prevent infinite loops
            self.narration_buffer.append(
                "[The chaos of battle becomes too complex to follow...]"
            )