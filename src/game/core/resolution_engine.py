class ResolutionEngine:
    """
    Executes ActionPlans mechanically. No LLM calls here—
    this is pure game logic.
    """
    
    def __init__(self, rules_engine: 'RulesEngine', state_manager: 'StateManager'):
        self.rules = rules_engine
        self.state = state_manager
    
    def execute_plan(self, resolution: Resolution) -> Resolution:
        """
        Execute an ActionPlan step by step.
        Returns the Resolution with all results populated.
        """
        plan = resolution.action_plan
        resolution.status = ResolutionStatus.AWAITING_ROLL
        
        # Process required rolls in order
        all_rolls = list(plan.required_rolls)
        roll_index = 0
        
        while roll_index < len(all_rolls):
            roll_spec = all_rolls[roll_index]
            
            # Execute the roll
            result = self.rules.execute_roll(roll_spec)
            resolution.roll_results.append(result)
            
            # Check for conditional follow-up rolls
            if result.success and roll_index in plan.conditional_rolls:
                # Insert conditional rolls right after this one
                conditional = plan.conditional_rolls[roll_index]
                for i, cond_roll in enumerate(conditional):
                    all_rolls.insert(roll_index + 1 + i, cond_roll)
            
            # Build narration fragment for this roll
            fragment = self._narrate_roll(result)
            resolution.narration_fragments.append(fragment)
            
            roll_index += 1
        
        # Determine overall success
        overall_success = self._evaluate_success(resolution)
        
        # Queue up appropriate state changes
        if overall_success:
            resolution.pending_state_changes = plan.on_success
        else:
            resolution.pending_state_changes = plan.on_failure
        
        # Check for triggered reactions
        resolution.triggered_reactions = self._check_reactions(
            plan, resolution, overall_success
        )
        
        resolution.status = ResolutionStatus.RESOLVED
        return resolution
    
    def _evaluate_success(self, resolution: Resolution) -> bool:
        """Determine if the action succeeded overall"""
        # Simple version: all required rolls must succeed
        # You might want more nuanced logic here
        if not resolution.roll_results:
            return True  # No rolls needed = auto-success
        
        # For attacks: first roll (attack) must succeed
        # Damage rolls don't affect "success"
        primary_rolls = [r for r in resolution.roll_results 
                        if r.spec.roll_type in (RollType.ATTACK, RollType.CHECK, 
                                                 RollType.SAVE, RollType.CONTEST)]
        return all(r.success for r in primary_rolls)
    
    def _check_reactions(self, plan: ActionPlan, resolution: Resolution, 
                         success: bool) -> List[Action]:
        """Check if any entities react to this action"""
        reactions = []
        
        for entity_id in plan.potential_reactions:
            entity = self.state.get_entity(entity_id)
            if entity and entity.has_reaction_to(plan.action_type, success):
                reaction = Action(
                    id=f"reaction_{entity_id}_{resolution.action_plan.actor_id}",
                    owner_id=entity_id,
                    intent_text=entity.get_reaction_intent(plan.action_type),
                    priority=100  # Reactions are high priority
                )
                reactions.append(reaction)
        
        return reactions
    
    def _narrate_roll(self, result: RollResult) -> str:
        """Generate a simple narration fragment for a roll"""
        # This is mechanical narration; the DM will embellish later
        if result.critical_success:
            return f"[CRITICAL SUCCESS] {result.spec.reason}: {result.natural_roll} (total: {result.total})"
        elif result.critical_failure:
            return f"[CRITICAL FAILURE] {result.spec.reason}: {result.natural_roll}"
        elif result.success:
            return f"[SUCCESS] {result.spec.reason}: rolled {result.total} vs {result.spec.dc or result.spec.target_ac}"
        else:
            return f"[FAILURE] {result.spec.reason}: rolled {result.total} vs {result.spec.dc or result.spec.target_ac}"