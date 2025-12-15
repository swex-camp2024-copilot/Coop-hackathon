import argparse
import importlib
import inspect
import os
import random
from typing import Optional

from bots.bot_interface import BotInterface
from simulator.match import run_match
from simulator.visualizer import Visualizer


def run_tournament(headless: bool = False):
    """Run a tournament with all bots from the bots folder.
    Returns the winner bot instance and tournament statistics.

    Args:
        headless (bool): If True, run without visualization
    """
    # Step 1: Find and load all bots
    bots = discover_bots()
    print(f"Found {len(bots)} bots for the tournament")
    for bot in bots:
        print(f"- {bot.name}")

    # Step 2: Run tournament rounds until we have a winner
    round_num = 1
    stats = {"matches": [], "rounds": []}

    # Keep track of losers and their total turns fought
    losers_stats = {}  # {bot_name: total_turns_fought}

    while len(bots) > 1:
        print(f"\n=== Round {round_num} ===")
        print(f"{len(bots)} bots competing in this round")

        # Create pairs for this round
        pairs, lucky_loser = create_pairs(bots, losers_stats)

        # Store round information
        round_info = {
            "round": round_num,
            "participants": [bot.name for bot in bots],
            "pairs": [
                (b1.name, b2.name) if b2 else (b1.name, lucky_loser.name if lucky_loser else None) for b1, b2 in pairs
            ],
            "lucky_loser": lucky_loser.name if lucky_loser else None,
        }
        stats["rounds"].append(round_info)

        # Run matches and collect winners
        winners = []
        for b1, b2 in pairs:
            if b2 is None:  # Odd number of bots, b1 gets a bye
                winners.append(b1)
                print(f"{b1.name} gets a bye")
                continue

            print(f"Match: {b1.name} vs {b2.name}")
            winner, logger = run_match(b1, b2)

            turns_fought = logger.get_snapshots()[-1]["turn"]  # Get the last turn number
            snapshots = logger.get_snapshots()

            if not headless:
                visualizer = Visualizer(logger, b1, b2)
                visualizer.run(snapshots, len(bots) > 2)

            draw_counter = 0
            while winner == "Draw":
                draw_counter += 1
                print("Match ended in a draw")
                winner, logger = run_match(b1, b2)

                snapshots = logger.get_snapshots()

                if not headless:
                    visualizer = Visualizer(logger, b1, b2)
                    visualizer.run(snapshots, len(bots) > 2)

                if draw_counter > 2:
                    break
                continue

            if draw_counter <= 2:
                # Update losers stats
                loser = b2 if winner == b1 else b1
                losers_stats[loser.name] = losers_stats.get(loser.name, 0) + turns_fought

                # Store match information
                match_info = {
                    "round": round_num,
                    "bot1": b1.name,
                    "bot2": b2.name,
                    "winner": winner,
                    "turns": turns_fought,
                }
                stats["matches"].append(match_info)

                winners.append(winner)
                print(f"Winner: {winner.name} after {turns_fought} turns")
            else:
                print(f"Too many draws, spell casters {b1.name} and  {b2.name} are disqualified")
                losers_stats[b1.name] = losers_stats.get(b1.name, 0) + turns_fought
                losers_stats[b2.name] = losers_stats.get(b2.name, 0) + turns_fought
                match_info = {
                    "round": round_num,
                    "bot1": b1.name,
                    "bot2": b2.name,
                    "winner": "NONE",
                    "turns": turns_fought,
                }
            stats["matches"].append(match_info)

        # Update bots for next round
        bots = winners
        round_num += 1

    # Tournament complete
    winner = bots[0]
    print(f"\n🏆 Tournament Winner: {winner.name} 🏆")

    return winner, stats


def discover_bots() -> list[BotInterface]:
    """Discover and instantiate all bots in the bots directory."""
    bots = []
    bots_dir = "bots"

    # Skip these directories as they don't contain bot implementations
    skip_dirs = {"__pycache__", "bot_interface"}

    for root, dirs, files in os.walk(bots_dir):
        # Skip interface and __pycache__ directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                # Construct the module path
                relative_path = os.path.relpath(root, os.getcwd())
                module_path = relative_path.replace(os.sep, ".") + "." + file[:-3]

                try:
                    # Import the module
                    module = importlib.import_module(module_path)

                    # Find classes that inherit from BotInterface
                    for _name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BotInterface) and obj.__module__ == module_path:
                            # Instantiate the bot and add to the list
                            bot_instance = obj()
                            bots.append(bot_instance)

                except Exception as e:
                    print(f"Error loading bot from {module_path}: {e}")

    return bots


def find_bot_by_name(name: str) -> Optional[BotInterface]:
    """Find and instantiate a bot by its name.
    Returns None if no bot with the given name is found.
    """
    all_bots = discover_bots()
    for bot in all_bots:
        if bot.name.lower() == name.lower():
            return bot
    return None


def list_available_bots():
    """List all available bots in the bots directory."""
    bots = discover_bots()
    print(f"Found {len(bots)} bots:")
    for bot in bots:
        print(f"- {bot.name}")
    return bots


def create_pairs(
    bots: list[BotInterface], losers_stats: dict[str, int]
) -> tuple[list[tuple[BotInterface, Optional[BotInterface]]], Optional[BotInterface]]:
    """Create pairs of bots for matches.
    Returns a list of pairs and the lucky loser bot (if needed).
    """
    # Make a copy and shuffle to create random pairs
    random.shuffle(bots)
    pairs = []
    lucky_loser = None

    # If odd number of bots, we need to find a "lucky loser"
    if len(bots) % 2 != 0 and losers_stats:
        # Find losers with the highest number of turns fought
        max_turns = max(losers_stats.values())
        candidates = [name for name, turns in losers_stats.items() if turns == max_turns]

        # Randomly select one if multiple candidates
        lucky_loser_name = random.choice(candidates)

        # Find the bot instance with this name
        for bot in bots:
            if bot.name == lucky_loser_name:
                lucky_loser = bot
                break

    # Create pairs
    for i in range(0, len(bots), 2):
        if i + 1 < len(bots):
            pairs.append((bots[i], bots[i + 1]))
        else:
            # This bot doesn't have a pair
            if lucky_loser:
                pairs.append((bots[i], lucky_loser))
            else:
                pairs.append((bots[i], None))  # Gets a bye

    return pairs, lucky_loser


def run_single_match(
    bot1_name: str,
    bot2_name: str,
    verbose: bool = False,
    headless: bool = False,
    count: int = 1,
    graph: bool = False,
):
    """Run matches between two bots with the given names.

    Args:
        bot1_name (str): Name of the first bot
        bot2_name (str): Name of the second bot
        verbose (bool): Whether to print detailed match logs
        headless (bool): Whether to run without visualization
        count (int): Number of matches to run
        graph (bool): Whether to display a graph of wins/losses over time
    """
    bot1 = find_bot_by_name(bot1_name)
    bot2 = find_bot_by_name(bot2_name)

    if not bot1:
        print(f"Bot '{bot1_name}' not found. Use 'python main.py match list' to see available bots.")
        return

    if not bot2:
        print(f"Bot '{bot2_name}' not found. Use 'python main.py match list' to see available bots.")
        return

    if count <= 0:
        print("Count must be a positive integer")
        return

    # Stats for multiple matches
    stats = {"bot1_wins": 0, "bot2_wins": 0, "draws": 0, "total_turns": 0}
    match_results = []  # Track results for each match: 'bot1', 'bot2', or 'draw'

    for match_num in range(1, count + 1):
        if count > 1:
            print(f"\nMatch {match_num}/{count}: {bot1.name} vs {bot2.name}")
        else:
            print(f"Match: {bot1.name} vs {bot2.name}")

        winner, logger = run_match(bot1, bot2, verbose=verbose)

        turns_fought = logger.get_snapshots()[-1]["turn"]  # Get the last turn number
        stats["total_turns"] += turns_fought

        if winner == bot1:
            stats["bot1_wins"] += 1
            match_results.append('bot1')
        elif winner == bot2:
            stats["bot2_wins"] += 1
            match_results.append('bot2')
        else:
            stats["draws"] += 1
            match_results.append('draw')

        # Only visualize if not headless and (single match or last match in a series)
        if not headless and (count == 1 or (match_num == count and count <= 5)):
            snapshots = logger.get_snapshots()
            visualizer = Visualizer(logger, bot1, bot2)
            visualizer.run(snapshots, False)

        print(f"Winner: {winner.name if winner != 'Draw' else 'Draw'} after {turns_fought} turns")

    # Print stats summary for multiple matches
    if count > 1:
        print("\n" + "=" * 50)
        print(f"MATCH RESULTS: {bot1.name} vs {bot2.name} ({count} matches)")
        print("=" * 50)
        bot1_win_pct = (stats["bot1_wins"] / count) * 100
        bot2_win_pct = (stats["bot2_wins"] / count) * 100
        draws_pct = (stats["draws"] / count) * 100
        avg_turns = stats["total_turns"] / count

        print(f"{bot1.name}: {stats['bot1_wins']} wins ({bot1_win_pct:.1f}%)")
        print(f"{bot2.name}: {stats['bot2_wins']} wins ({bot2_win_pct:.1f}%)")
        print(f"Draws: {stats['draws']} ({draws_pct:.1f}%)")
        print(f"Average match length: {avg_turns:.1f} turns")
        
        # Display graph if requested
        if graph:
            display_match_graph(match_results, bot1.name, bot2.name)


def display_match_graph(match_results: list[str], bot1_name: str, bot2_name: str):
    """Display a text-based graph showing wins/losses over the course of matches.
    
    Args:
        match_results (list[str]): List of match results ('bot1', 'bot2', or 'draw')
        bot1_name (str): Name of the first bot
        bot2_name (str): Name of the second bot
    """
    if not match_results:
        return
    
    print("\n" + "=" * 80)
    print("MATCH PROGRESSION GRAPH - CUMULATIVE WINS OVER TIME")
    print("=" * 80)
    
    # Calculate running wins for each bot
    bot1_running_wins = []
    bot2_running_wins = []
    bot1_wins = 0
    bot2_wins = 0
    
    for result in match_results:
        if result == 'bot1':
            bot1_wins += 1
        elif result == 'bot2':
            bot2_wins += 1
        bot1_running_wins.append(bot1_wins)
        bot2_running_wins.append(bot2_wins)
    
    # Determine graph dimensions
    max_wins = max(bot1_wins, bot2_wins, 1)
    graph_height = min(25, max_wins + 1)
    graph_width = len(match_results)
    
    # Legend
    print(f"\nLegend:")
    print(f"  * = {bot1_name}")
    print(f"  # = {bot2_name}")
    print(f"  + = Both bots tied at this point")
    print()
    print(f"Y-Axis (↑) = Total Wins    X-Axis (→) = Match Number")
    print()
    
    # Draw the graph from top to bottom
    for row in range(graph_height, -1, -1):
        # Y-axis label with better description
        if row == graph_height:
            print(f"{row:3d} |", end="")
        elif row == graph_height // 2:
            print(f"{row:3d} | ← Total Wins", end="")
            # Pad to maintain alignment
            for _ in range(graph_width):
                print(" ", end="")
            print()
            print(f"    |", end="")
        else:
            print(f"{row:3d} |", end="")
        
        # Plot points for each match
        for i in range(graph_width):
            bot1_val = bot1_running_wins[i]
            bot2_val = bot2_running_wins[i]
            
            # Determine what character to display
            char = " "
            
            if bot1_val == row and bot2_val == row:
                char = "+"  # Tied
            elif bot1_val == row and bot2_val == row - 1:
                char = "+"  # Close together
            elif bot1_val == row - 1 and bot2_val == row:
                char = "+"  # Close together
            elif bot1_val == row:
                char = "*"  # Bot1 at this level
            elif bot2_val == row:
                char = "#"  # Bot2 at this level
            
            print(char, end="")
        
        print()  # New line
    
    # X-axis
    print("    +" + "-" * graph_width)
    print("     ", end="")
    
    # X-axis labels (match numbers) - show every 5th or 10th depending on width
    if graph_width <= 50:
        step = 5
    elif graph_width <= 100:
        step = 10
    else:
        step = 20
    
    for i in range(graph_width):
        match_num = i + 1
        if match_num == 1 or match_num % step == 0:
            # Calculate how many digits to print
            num_str = str(match_num)
            print(num_str[0], end="")
        else:
            print(" ", end="")
    
    print()
    print("     Matches →")
    
    # Add detailed explanation
    print()
    print("=" * 80)
    print("HOW TO READ THIS GRAPH:")
    print("=" * 80)
    print("• The Y-axis (vertical) shows the TOTAL NUMBER OF WINS accumulated")
    print("• The X-axis (horizontal) shows the MATCH NUMBER (1st match, 2nd match, etc.)")
    print(f"• Each '*' shows where {bot1_name} had that many wins at that match")
    print(f"• Each '#' shows where {bot2_name} had that many wins at that match")
    print("• The lines climb UP as each bot wins more matches")
    print("• Flat sections = no wins (either draws or the other bot won)")
    print()
    
    # Summary
    print(f"Final Scores:")
    print(f"  {bot1_name}: {bot1_wins} wins")
    print(f"  {bot2_name}: {bot2_wins} wins")
    
    # Show who is leading
    if bot1_wins > bot2_wins:
        lead = bot1_wins - bot2_wins
        print(f"  → {bot1_name} leads by {lead} win(s)")
    elif bot2_wins > bot1_wins:
        lead = bot2_wins - bot1_wins
        print(f"  → {bot2_name} leads by {lead} win(s)")
    else:
        print(f"  → Tied!")
    print()


def parse_arguments():
    """Parse command line arguments for the application."""
    parser = argparse.ArgumentParser(description="Wizard Battle Tournament")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Tournament command
    tournament_parser = subparsers.add_parser("tournament", help="Run a full tournament with all bots")
    tournament_parser.add_argument("--headless", action="store_true", help="Run without visualization")

    # Match command
    match_parser = subparsers.add_parser("match", help="Run a single match between two bots or list available bots")
    match_parser.add_argument("bot1", nargs="?", help="Name of the first bot")
    match_parser.add_argument("bot2", nargs="?", help="Name of the second bot")
    match_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed match logs")
    match_parser.add_argument("--headless", action="store_true", help="Run without visualization")
    match_parser.add_argument("--count", "-c", type=int, default=1, help="Number of matches to run")
    match_parser.add_argument("--graph", "-g", action="store_true", help="Display a graph of wins/losses over matches")

    return parser.parse_args()


def main():
    """Main entry point for the Spellcasters game."""
    args = parse_arguments()

    if args.command == "tournament" or args.command is None:
        # Run the full tournament
        headless = getattr(args, "headless", False)
        winner, stats = run_tournament(headless=headless)
        print(f"Tournament completed with {len(stats['matches'])} matches across {len(stats['rounds'])} rounds")

    elif args.command == "match":
        if args.bot1 == "list" or (args.bot1 is None and args.bot2 is None):
            # List available bots
            list_available_bots()
        elif args.bot1 and args.bot2:
            # Run a match between two specific bots
            headless = getattr(args, "headless", False)
            count = getattr(args, "count", 1)
            graph = getattr(args, "graph", False)
            run_single_match(args.bot1, args.bot2, args.verbose, headless=headless, count=count, graph=graph)
        else:
            print("Please provide two bot names or use 'list' to see available bots.")
            print("Usage: python main.py match <bot1> <bot2> [--headless] [--verbose] [--count N] [--graph]")
            print("       python main.py match list")


# Example usage
if __name__ == "__main__":
    main()
