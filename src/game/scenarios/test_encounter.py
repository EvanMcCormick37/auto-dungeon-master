"""
Test encounter utility for generating sample game states.
"""
from src.game.models import GameState, PlayerCharacter, Entity, Room, Level, Item, AttackStats, Attributes, Attribute, Status


def create_test_encounter() -> GameState:
    """
    Creates a test encounter: Ron Jeremy (level 3 barbarian) vs 3 goblins
    in a dark cathedral chamber.
    
    Returns:
        GameState: A fully populated game state ready for testing
    """
    
    # ==================== ITEMS ====================
    
    # Player's equipped weapon
    greataxe = Item(
        id="item_greataxe_001",
        name="Greataxe",
        description="A massive two-handed axe with a wickedly sharp blade",
        hp=(8, 8),  # Item durability (current, max)
        cost=30,
        weight=7,
        effects=[],
        attack_stats=AttackStats(
            range=0,
            base_attribute=Attribute.STR,
            damage="1d12"
        )
    )
    
    # Player's inventory items
    mess_kit = Item(
        id="item_messkit_001",
        name="Mess Kit",
        description="Tin cooking and eating utensils",
        hp=(6, 6),
        cost=2,
        weight=1,
        effects=[],
        attack_stats=None
    )
    
    rope = Item(
        id="item_rope_001",
        name="Hempen Rope (50ft)",
        description="Sturdy rope, useful for climbing and restraining",
        hp=(6, 6),
        cost=1,
        weight=10,
        effects=[],
        attack_stats=None
    )
    
    net = Item(
        id="item_net_001",
        name="Net",
        description="A weighted throwing net for entangling foes",
        hp=(6, 6),
        cost=1,
        weight=3,
        effects=[],
        attack_stats=AttackStats(
            range=15,
            base_attribute=Attribute.DEX,
            damage="0"  # No damage, restraining weapon
        )
    )
    
    oil_jar = Item(
        id="item_oil_001",
        name="Jar of Oil",
        description="Flask of slippery oil, highly flammable",
        hp=(6, 6),
        cost=1,
        weight=1,
        effects=[],
        attack_stats=None
    )
    
    # Goblin weapons
    crossbow = Item(
        id="item_crossbow_001",
        name="Light Crossbow",
        description="A compact ranged weapon",
        hp=(6, 6),
        cost=25,
        weight=5,
        effects=[],
        attack_stats=AttackStats(
            range=80,
            base_attribute=Attribute.DEX,
            damage="1d8"
        )
    )
    
    spear = Item(
        id="item_spear_001",
        name="Spear",
        description="A simple wooden spear with an iron tip",
        hp=(6, 6),
        cost=1,
        weight=3,
        effects=[],
        attack_stats=AttackStats(
            range=20,  # Can be thrown
            base_attribute=Attribute.STR,
            damage="1d6"
        )
    )
    
    long_knife = Item(
        id="item_longknife_001",
        name="Long Knife",
        description="A crude but sharp blade",
        hp=(6, 6),
        cost=5,
        weight=2,
        effects=[],
        attack_stats=AttackStats(
            range=5,
            base_attribute=Attribute.DEX,
            damage="1d4"
        )
    )
    
    # ==================== PLAYER CHARACTER ====================
    
    # Barbarian Rage status (as an example feat/condition)
    rage_feat = Status(
        id="feat_rage",
        name="Rage",
        description="Barbarian's primal fury grants bonus damage and resistance",
        bonuses=Attributes(
            STR=2,
            DEX=0,
            CON=2,
            INT=0,
            WIS=0,
            CHA=0
        ),
        is_feat=True
    )
    
    player = PlayerCharacter(
        _class="Barbarian",
        level=3,
        attributes=Attributes(
            STR=18,  # +4 modifier - excellent for barbarian
            DEX=14,  # +2 modifier - decent
            CON=16,  # +3 modifier - high HP
            INT=8,   # -1 modifier - barbarians aren't scholars
            WIS=12,  # +1 modifier - average perception
            CHA=10   # +0 modifier - average
        ),
        max_hp=31,  # 12 + (2d12 + 3 CON per level) = 12 + 9 + 10 = 31
        ac=14,      # 10 + 2 (DEX) + 2 (Unarmored Defense with CON)
        capacity=270,  # STR * 15 = 18 * 15
        feats=[rage_feat],
        xp=(900, 2700),  # Current XP, Next level XP
        gold=45,
        inventory=[mess_kit, rope, net, oil_jar],
        equipped=[greataxe],
        spell_slots=None,  # Barbarians don't cast spells
        conditions=[],  # No active conditions at start
        hp=31  # Full health at start
    )
    
    # ==================== GOBLINS ====================
    
    goblin_1 = Entity(
        id="entity_goblin_001",
        name="Goblin Sniper",
        description="A scrawny green humanoid with yellow eyes and a crossbow",
        xp=50,
        attributes=Attributes(
            STR=8,
            DEX=14,
            CON=10,
            INT=10,
            WIS=8,
            CHA=8
        ),
        max_hp=7,
        ac=15,  # 10 + 2 DEX + 3 (leather armor)
        hp=7,
        disposition="hostile",
        conditions=[],
        inventory=[],
        equipped=[crossbow]
    )
    
    goblin_2 = Entity(
        id="entity_goblin_002",
        name="Goblin Warrior",
        description="A battle-scarred goblin gripping a spear defensively",
        xp=50,
        attributes=Attributes(
            STR=10,  # +0 modifier
            DEX=14,  # +2 modifier
            CON=10,  # +0 modifier
            INT=10,
            WIS=8,
            CHA=8
        ),
        max_hp=7,
        ac=15,
        hp=7,
        disposition="hostile",
        conditions=[],
        inventory=[],
        equipped=[spear]
    )
    
    goblin_3 = Entity(
        id="entity_goblin_003",
        name="Goblin Rogue",
        description="A sneaky goblin clutching a long knife, eyes darting about",
        xp=50,
        attributes=Attributes(
            STR=8,
            DEX=16,  # +3 modifier - very nimble
            CON=10,
            INT=10,
            WIS=8,
            CHA=8
        ),
        max_hp=7,
        ac=15,
        hp=7,
        disposition="hostile",
        conditions=[],
        inventory=[],
        equipped=[long_knife]
    )
    
    # ==================== LOCATION ====================
    
    # Environmental items in the room
    torch_item = Item(
        id="item_torch_001",
        name="Torch (Brazier)",
        description="A dimly lit torch mounted in an ornate brazier",
        hp=(4, 4),
        cost=0,
        weight=1,
        effects=[],
        attack_stats=None
    )
    
    cathedral_chamber = Room(
        id="room_cathedral_001",
        name="Cathedral Chamber",
        description=(
            "A vast, shadowy chamber with soaring vaulted ceilings that disappear "
            "into darkness above. Four braziers mounted on the walls cast flickering "
            "light that barely pierces the gloom, creating dancing shadows among the "
            "ancient stone pillars. The air smells of dust and old incense. Three "
            "goblins have taken defensive positions among the pillars."
        ),
        is_explored=True,  # Player is already here
        occupants=[goblin_1, goblin_2, goblin_3],
        items=[torch_item]  # Could be grabbed/used as improvised weapon
    )
    
    # ==================== LEVEL ====================
    
    dungeon_level = Level(
        id="level_catacombs_001",
        name="Ancient Catacombs",
        description="A forgotten underground complex beneath an abandoned temple",
        room_ids=["room_cathedral_001"],  # More rooms would be added in full game
        effects=[]  # Could have level-wide effects like "dim light" or "cursed"
    )
    
    # ==================== GAME STATE ====================
    
    game_state = GameState(
        player=player,
        level=dungeon_level,
        location=cathedral_chamber,
        recent_actions=[
            "Descended the ancient staircase",
            "Entered the cathedral chamber",
            "Spotted three goblins lurking in the shadows",
        ]
    )
    
    return game_state


def print_encounter_summary(state: GameState) -> None:
    """
    Print a human-readable summary of the encounter.
    
    Args:
        state: The game state to summarize
    """
    print("=" * 60)
    print("TEST ENCOUNTER SUMMARY")
    print("=" * 60)
    print()
    
    # Player info
    pc = state.player
    print(f"PLAYER: {pc._class} (Level {pc.level})")
    print(f"  HP: {pc.hp}/{pc.max_hp} | AC: {pc.ac}")
    print(f"  STR: {pc.attributes['STR']} | DEX: {pc.attributes['DEX']} | CON: {pc.attributes['CON']}")
    print(f"  Equipped: {', '.join(item.name for item in pc.equipped)}")
    print(f"  Inventory: {', '.join(item.name for item in pc.inventory)}")
    print()
    
    # Location info
    print(f"LOCATION: {state.location.name}")
    print(f"  {state.location.description}")
    print()
    
    # Enemies
    print(f"ENEMIES ({len(state.location.occupants)}):")
    for entity in state.location.occupants:
        weapon = entity.equipped[0].name if entity.equipped else "None"
        print(f"  - {entity.name}")
        print(f"    HP: {entity.hp}/{entity.max_hp} | AC: {entity.ac} | Weapon: {weapon}")
    print()
    
    # Recent actions
    print("RECENT ACTIONS:")
    for action in state.recent_actions:
        print(f"  - {action}")
    print()
    print("=" * 60)


# Example usage
if __name__ == "__main__":
    encounter = create_test_encounter()
    print_encounter_summary(encounter)