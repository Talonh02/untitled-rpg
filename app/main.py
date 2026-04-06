"""
Entry point and terminal UI for the RPG.
Uses the 'rich' library for styled terminal output.
"""
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt
from rich.style import Style
from rich import box

from app.data import GameState, Player, NPC, World, WEAPONS, ARMOR


# ============================================================
# TERMINAL UI — all display logic lives here
# ============================================================

class TerminalUI:
    """
    Handles all terminal display. Every kind of text (narration, dialogue,
    combat, system messages) gets its own style so the game feels alive.
    """

    def __init__(self):
        self.console = Console()
        # Define styles for different kinds of text
        self.narration_style = Style(color="white", italic=True)
        self.dialogue_style = Style(color="bright_cyan")
        self.combat_style = Style(color="red", bold=True)
        self.system_style = Style(color="bright_black")
        self.status_style = Style(color="yellow", dim=True)

    def show_splash(self):
        """Show the game title screen."""
        title = Text()
        title.append("\n")
        title.append("  ╔══════════════════════════════════════╗\n", style="bold yellow")
        title.append("  ║                                      ║\n", style="bold yellow")
        title.append("  ║        U N T I T L E D   R P G       ║\n", style="bold bright_white")
        title.append("  ║                                      ║\n", style="bold yellow")
        title.append("  ║     Where models speak and           ║\n", style="dim white")
        title.append("  ║       Python thinks.                 ║\n", style="dim white")
        title.append("  ║                                      ║\n", style="bold yellow")
        title.append("  ╚══════════════════════════════════════╝\n", style="bold yellow")
        self.console.print(title)

    def show_menu(self) -> str:
        """
        Show the main menu and return the player's choice.
        Returns: "new", "load", or "quit"
        """
        self.console.print()
        self.console.print("  [bold]1.[/bold] New Game", style="white")
        self.console.print("  [bold]2.[/bold] Load Game", style="white")
        self.console.print("  [bold]3.[/bold] Quit", style="white")
        self.console.print()

        choice = Prompt.ask("  Choose", choices=["1", "2", "3"], default="1")
        if choice == "1":
            return "new"
        elif choice == "2":
            return "load"
        else:
            return "quit"

    def show_narration(self, text: str):
        """Show narrator prose — italic, slightly dimmed for that literary feel."""
        if not text:
            return
        self.console.print()
        self.console.print(Panel(
            Text(text, style=self.narration_style),
            border_style="dim white",
            box=box.SIMPLE,
            padding=(0, 2),
        ))

    def show_npc_dialogue(self, npc_name: str, text: str):
        """Show NPC dialogue with their name as a header."""
        if not text:
            return
        self.console.print()
        self.console.print(Panel(
            Text(text, style=self.dialogue_style),
            title=f"[bold bright_cyan]{npc_name}[/bold bright_cyan]",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        ))

    def show_combat(self, text: str):
        """Show combat narration — bold red for intensity."""
        if not text:
            return
        self.console.print()
        self.console.print(Panel(
            Text(text, style=self.combat_style),
            border_style="red",
            box=box.HEAVY,
            padding=(0, 2),
        ))

    def show_system(self, text: str):
        """Show system messages — dim gray, unobtrusive."""
        self.console.print(text, style=self.system_style)

    def show_status_bar(self, player: Player, world: World):
        """
        Show a compact status bar at the bottom with key info.
        Health, hunger, location, time, coins.
        """
        # Build the status line
        loc = world.locations.get(player.location)
        loc_name = loc.name if loc else "???"

        # Health color based on value
        if player.health > 60:
            health_str = f"[green]HP:{player.health}[/green]"
        elif player.health > 30:
            health_str = f"[yellow]HP:{player.health}[/yellow]"
        else:
            health_str = f"[red]HP:{player.health}[/red]"

        # Hunger indicator
        if player.hunger > 60:
            hunger_str = f"[red]Hungry[/red]"
        elif player.hunger > 30:
            hunger_str = f"[yellow]Peckish[/yellow]"
        else:
            hunger_str = ""

        weapon_display = WEAPONS.get(player.weapon, {}).get("display", player.weapon)
        time_str = f"{world.time_slot.capitalize()}, Day {world.current_day}"

        parts = [
            health_str,
            hunger_str,
            f"[dim]{loc_name}[/dim]",
            f"[dim]{time_str}[/dim]",
            f"[yellow]{player.coins}c[/yellow]",
            f"[dim]{weapon_display}[/dim]",
        ]
        # Filter out empty parts
        status = "  |  ".join(p for p in parts if p)

        self.console.print(f"\n  {status}", highlight=False)

    def get_input(self) -> str:
        """Get player input with a styled prompt."""
        try:
            self.console.print()
            text = Prompt.ask("[bold white]>[/bold white]")
            return text.strip() if text else ""
        except (EOFError, KeyboardInterrupt):
            return ""

    def show_inventory(self, player: Player):
        """Show the player's inventory and equipment in a formatted table."""
        self.console.print()

        # Equipment
        weapon_display = WEAPONS.get(player.weapon, {}).get("display", player.weapon)
        armor_display = ARMOR.get(player.armor, {}).get("display", player.armor)

        table = Table(title="Inventory", box=box.SIMPLE, style="dim white",
                      title_style="bold white")
        table.add_column("Item", style="white")
        table.add_column("Details", style="dim white")

        table.add_row("Weapon", weapon_display)
        table.add_row("Armor", armor_display)
        table.add_row("Coins", str(player.coins))
        table.add_row("───", "───")

        if player.inventory:
            for item in player.inventory:
                table.add_row(str(item), "")
        else:
            table.add_row("[dim]nothing else[/dim]", "")

        self.console.print(table)

    def show_companion_status(self, companions: list):
        """Show companion info — health, trust, mood."""
        if not companions:
            self.console.print("  You travel alone.", style=self.system_style)
            return

        self.console.print()
        table = Table(title="Companions", box=box.SIMPLE, style="dim white",
                      title_style="bold white")
        table.add_column("Name", style="white")
        table.add_column("Health", style="green")
        table.add_column("Trust", style="cyan")
        table.add_column("Mood", style="dim white")

        for npc in companions:
            health = npc.stats.health
            trust = npc.relationship.trust if npc.relationship else 0
            mood = npc.temperament

            # Color code health
            if health > 60:
                health_str = f"[green]{health}[/green]"
            elif health > 30:
                health_str = f"[yellow]{health}[/yellow]"
            else:
                health_str = f"[red]{health}[/red]"

            table.add_row(npc.name, health_str, f"{trust:.0f}", mood)

        self.console.print(table)

    def show_character_creation_result(self, player: Player):
        """Show the newly created character's details."""
        self.console.print()
        self.console.print(Panel(
            f"[bold]{player.name}[/bold]\n\n"
            f"{player.backstory}\n\n"
            f"[dim]Weapon: {WEAPONS.get(player.weapon, {}).get('display', player.weapon)}  |  "
            f"Armor: {ARMOR.get(player.armor, {}).get('display', player.armor)}  |  "
            f"Coins: {player.coins}[/dim]",
            title="[bold yellow]Your Character[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2),
        ))


# ============================================================
# MAIN — the entry point
# ============================================================

def main():
    """
    Main function — shows splash screen, handles menu,
    starts the game loop.
    """
    ui = TerminalUI()

    try:
        ui.show_splash()
        choice = ui.show_menu()

        if choice == "quit":
            ui.show_system("Farewell.")
            return

        if choice == "load":
            _handle_load_game(ui)
            return

        if choice == "new":
            _handle_new_game(ui)
            return

    except KeyboardInterrupt:
        ui.console.print("\n")
        ui.show_system("Game interrupted. Farewell.")
    except Exception as e:
        ui.console.print(f"\n[red]Fatal error: {e}[/red]")
        raise


def _handle_new_game(ui: TerminalUI):
    """Set up a new game — world generation, character creation, then start playing."""
    ui.show_system("\n  Starting a new game...\n")

    # 1. Character creation
    player_name = Prompt.ask("  [bold]What is your name?[/bold]")
    if not player_name:
        player_name = "Stranger"

    ui.console.print()
    ui.console.print("  [bold]How would you like to create your character?[/bold]")
    ui.console.print("  [bold]1.[/bold] Describe yourself (AI creates your character)")
    ui.console.print("  [bold]2.[/bold] Pick an archetype (quick start)")
    ui.console.print()

    creation_choice = Prompt.ask("  Choose", choices=["1", "2"], default="2")

    # 2. Generate or load the world
    ui.show_system("\n  Generating world... (this may take a moment)")
    game_state = GameState()

    # Try to generate a world via the engine
    try:
        from app.engine.world import generate_starter_world
        game_state.world = generate_starter_world()
        ui.show_system(f"  World created: {game_state.world.name}")
    except Exception as e:
        ui.show_system(f"  World generation not available ({e}). Using placeholder world.")
        game_state.world = _placeholder_world()

    # 3. Create the player
    if creation_choice == "1":
        ui.console.print()
        description = Prompt.ask(
            "  [bold]Describe yourself[/bold] (real traits — the AI will translate them)\n  "
        )
        ui.show_system("  Creating your character...")
        try:
            from app.game.player import create_player_custom
            player = create_player_custom(player_name, description, game_state.world)
        except Exception:
            from app.game.player import create_player_quick
            player = create_player_quick(player_name, "wanderer", game_state.world)
    else:
        # Show archetype options
        from app.game.player import create_player_quick, get_archetype_list
        archetypes = get_archetype_list()

        ui.console.print()
        for idx, arch in enumerate(archetypes, 1):
            ui.console.print(f"  [bold]{idx}.[/bold] {arch['name']} — {arch['description']}")
        ui.console.print()

        arch_choice = Prompt.ask("  Choose", default="1")
        try:
            arch_idx = int(arch_choice) - 1
            arch_key = archetypes[arch_idx]["key"]
        except (ValueError, IndexError):
            arch_key = "wanderer"

        player = create_player_quick(player_name, arch_key, game_state.world)

    game_state.player = player
    ui.show_character_creation_result(player)

    # 4. Start the game loop
    ui.console.print()
    ui.show_system("  Press Enter to begin your journey...")
    input()

    from app.game.loop import GameLoop
    loop = GameLoop(game_state, ui)
    loop.run()


def _handle_load_game(ui: TerminalUI):
    """Load a saved game and resume playing."""
    save_path = "saves/save.json"

    if not os.path.exists(save_path):
        ui.show_system("  No save file found. Starting a new game instead.")
        _handle_new_game(ui)
        return

    ui.show_system(f"  Loading from {save_path}...")
    try:
        from app.game.state import load_game
        game_state = load_game(save_path)
        ui.show_system(f"  Loaded! Playing as {game_state.player.name}, "
                       f"turn {game_state.turn_number}.")

        from app.game.loop import GameLoop
        loop = GameLoop(game_state, ui)
        loop.run()
    except Exception as e:
        ui.show_system(f"  Failed to load: {e}")
        ui.show_system("  Starting a new game instead.")
        _handle_new_game(ui)


def _placeholder_world() -> World:
    """
    Create a minimal placeholder world so the game can run
    even if world generation fails. Just enough to walk around in.
    """
    from app.data import Location, NPC, Stats

    world = World(
        name="The Unnamed Realm",
        era="Age of Uncertainty",
        tone="grim but not hopeless",
        themes=["survival", "trust", "what makes a person"],
    )

    # A small starting town
    town_id = "haven"
    world.locations[town_id] = Location(
        id=town_id, name="Haven", type="city",
        description="A small town on the edge of something larger. "
                    "Smoke rises from chimneys. People move with purpose.",
        children_ids=["haven_square"],
        population=4200,
    )
    world.locations["haven_square"] = Location(
        id="haven_square", name="Town Square", type="district",
        description="An open square with a well at its center. "
                    "A few vendors are packing up for the evening.",
        parent_id=town_id,
        children_ids=["haven_tavern", "haven_market"],
        population=800,
    )
    world.locations["haven_tavern"] = Location(
        id="haven_tavern", name="The Quiet Drum", type="building",
        description="A tavern. Low ceiling, warm light, the smell of bread and ale. "
                    "A few people sit at tables. A dog sleeps by the fire.",
        parent_id="haven_square",
        population=25,
    )
    world.locations["haven_market"] = Location(
        id="haven_market", name="Market Row", type="building",
        description="A narrow street lined with merchant stalls. "
                    "Most are closed, but a few lanterns still flicker.",
        parent_id="haven_square",
        population=150,
    )

    # A few NPCs to populate the town
    world.npcs["npc_barkeep"] = NPC(
        id="npc_barkeep", name="Thom", age=52, fate=0.1,
        stats=Stats(strength=50, toughness=55, agility=35,
                    intelligence=45, depth=38, wisdom=55,
                    perception=60, willpower=50, education=25,
                    creativity=30, charisma=55, empathy=50,
                    courage=45, honesty=60, humor=50,
                    stubbornness=55, ambition=25, loyalty=65),
        occupation="barkeeper", social_class="working", wealth=45,
        temperament="calm", location="haven_tavern",
    )

    world.npcs["npc_merchant"] = NPC(
        id="npc_merchant", name="Sela Voss", age=34, fate=0.15,
        stats=Stats(strength=30, toughness=35, agility=45,
                    intelligence=58, depth=42, wisdom=40,
                    perception=65, willpower=40, education=50,
                    creativity=35, charisma=62, empathy=45,
                    courage=30, honesty=50, humor=40,
                    stubbornness=45, ambition=70, loyalty=40),
        occupation="merchant", social_class="merchant", wealth=65,
        temperament="cheerful", location="haven_market",
    )

    world.npcs["npc_stranger"] = NPC(
        id="npc_stranger", name="Dara", age=28, fate=0.5,
        stats=Stats(strength=40, toughness=45, agility=60,
                    intelligence=72, depth=78, wisdom=55,
                    perception=70, willpower=65, education=60,
                    creativity=68, charisma=50, empathy=70,
                    courage=55, honesty=45, humor=35,
                    stubbornness=60, ambition=40, loyalty=55),
        occupation="traveler", social_class="working", wealth=20,
        temperament="melancholy", location="haven_tavern",
        backstory="She arrived three days ago and hasn't said much to anyone.",
        secret="She's running from something. Or someone.",
    )

    world.current_day = 1
    world.time_slot = "evening"
    world.season = "autumn"

    return world
