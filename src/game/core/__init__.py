from src.game.llm import gm_oracle, narrator_oracle
from src.game.core.action_queue import ActionQueue
from src.game.core.resolution_engine import ResolutionEngine
from src.game.core.rules_engine import RulesEngine
from src.game.core.state_manager import StateManager
from src.game.core.game_controller import GameController
from src.game.models import GameState

rules_engine = RulesEngine()

def initialize_game_controller(
    initial_state: GameState
) -> GameController:
    """Instantiate all game components and return the GameController."""
    
    # Initialize core systems
    state_manager = StateManager(initial_state=initial_state)
    resolution_engine = ResolutionEngine(rules_engine=rules_engine, state_manager=state_manager)
    # Create and return the game controller
    controller = GameController(
        gm_oracle=gm_oracle,
        resolution_engine=resolution_engine,
        state_manager=state_manager,
        narrator_oracle=narrator_oracle
    )
    
    return controller

__all__ = [
    'ActionQueue',
    'ResolutionEngine',
    'StateManager',
    'GameController',
    'rules_engine',
    'initialize_game_controller'
]