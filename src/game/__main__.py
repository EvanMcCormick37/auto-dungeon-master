# Update src/auto-dungeon/__main__.py
"""Entry point for the dungeon crawler application."""

from src.game.config.settings import settings
from src.game.utils.logging import setup_logging
from src.game.core import initialize_game_controller, GameController
from src.game.scenarios import create_test_encounter


# ─────────────────────────────────────────────────────────────────────────────
# Game Loop
# ─────────────────────────────────────────────────────────────────────────────
def get_player_input() -> str | None:
    """Get input from the player, handling EOF and interrupts."""
    try:
        text = input("\n> ").strip()
        return text if text else None
    except (EOFError, KeyboardInterrupt):
        return "quit"


def game_loop(controller: GameController) -> None:
    """Main game loop - process player input until quit."""
    
    while True:
        player_input = get_player_input()
        
        if player_input is None:
            print("(Type something")
            continue
        
        # Handle meta commands
        command_lower = player_input.lower()
        
        if command_lower in ("quit", "exit", "q"):
            print("Thank you for playing!")
            break
        
        # Process game action
        try:
            response = controller.process_player_input(player_input)
            print(f"\n{response}")
                
        except Exception as e:
            print(f"\n[ERROR] Something went wrong: {e}")
            print("[The game attempts to recover...]")


def main() -> None:
    """Main entry point."""
    # Setup logging
    logger = setup_logging(
        level=settings.log_level,
        log_file=settings.log_file,
        enable_color=settings.enable_color,
    )
    
    logger.info("Starting Dungeon Crawler")
    logger.debug(f"Configuration: {settings}")
    
    # Initialize test encounter
    game_controller = initialize_game_controller(create_test_encounter())
    print("Welcome to Auto-Dungeon! This is a test encounter.")
    game_loop(game_controller)
    

if __name__ == "__main__":
    main()