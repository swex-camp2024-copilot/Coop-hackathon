import random
import json
import os
from collections import defaultdict

from bots.bot_interface import BotInterface


class UltimateBot(BotInterface):
    def __init__(self):
        self._name = "Enhanced Ultimate Self Learning Bot"
        self._sprite_path = "assets/wizards/coop-rg-2-bot.png"
        self._minion_sprite_path = "assets/minions/minion-rg-2.png"
        self._first_round = True
        
        # Learning system
        self._learning_file = "bots/enhanced_ultimate_self_learning_bot/learning_data.json"
        self._game_history = []  # Current game moves and outcomes
        self._learning_data = self._load_learning_data()
        
        # Strategy weights (will be adjusted through learning)
        self._strategy_weights = self._learning_data.get("strategy_weights", {
            "aggression": 1.0,
            "defense": 1.0,
            "resource_priority": 1.0,
            "positioning": 1.0,
            "spell_preference": {
                "melee_attack": 1.0,
                "fireball": 1.0,
                "heal": 1.0,
                "shield": 1.0,
                "summon": 1.0,
                "teleport": 1.0
            }
        })
        
        # Performance tracking
        self._stats = self._learning_data.get("stats", {
            "games_played": 0,
            "games_won": 0,
            "total_damage_dealt": 0,
            "total_damage_taken": 0,
            "spell_success_rate": defaultdict(lambda: {"used": 0, "effective": 0})
        })
        
        # Situational learning (state -> action -> outcome)
        self._situation_outcomes = self._learning_data.get("situation_outcomes", {})

    @property
    def name(self):
        return self._name

    @property
    def sprite_path(self):
        return self._sprite_path

    @property
    def minion_sprite_path(self):
        return self._minion_sprite_path

    def _load_learning_data(self):
        """Load learning data from file or return defaults"""
        if os.path.exists(self._learning_file):
            try:
                with open(self._learning_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading learning data: {e}")
                return {}
        return {}

    def _save_learning_data(self):
        """Persist learning data to file"""
        try:
            os.makedirs(os.path.dirname(self._learning_file), exist_ok=True)
            data = {
                "strategy_weights": self._strategy_weights,
                "stats": self._stats,
                "situation_outcomes": self._situation_outcomes
            }
            with open(self._learning_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving learning data: {e}")

    def _categorize_situation(self, state):
        """Categorize current game situation for learning"""
        self_data = state["self"]
        opp_data = state["opponent"]
        
        hp_category = "critical" if self_data["hp"] <= 40 else "low" if self_data["hp"] <= 70 else "healthy"
        mana_category = "low" if self_data["mana"] <= 40 else "medium" if self_data["mana"] <= 70 else "high"
        
        distance = max(
            abs(self_data["position"][0] - opp_data["position"][0]),
            abs(self_data["position"][1] - opp_data["position"][1])
        )
        distance_category = "close" if distance <= 3 else "medium" if distance <= 6 else "far"
        
        opp_hp_category = "low" if opp_data["hp"] <= 50 else "high"
        
        return f"{hp_category}_{mana_category}_{distance_category}_{opp_hp_category}"

    def _record_action(self, state, action):
        """Record action taken in current game"""
        situation = self._categorize_situation(state)
        self._game_history.append({
            "situation": situation,
            "action": action,
            "hp_before": state["self"]["hp"],
            "mana_before": state["self"]["mana"],
            "opp_hp_before": state["opponent"]["hp"]
        })

    def _learn_from_game(self, won):
        """Update learning data based on game outcome"""
        self._stats["games_played"] += 1
        if won:
            self._stats["games_won"] += 1
        
        win_rate = self._stats["games_won"] / self._stats["games_played"]
        
        # Learn from each action in the game
        for i, record in enumerate(self._game_history):
            situation = record["situation"]
            action = record["action"]
            
            # Initialize situation if new
            if situation not in self._situation_outcomes:
                self._situation_outcomes[situation] = {}
            
            action_key = self._serialize_action(action)
            if action_key not in self._situation_outcomes[situation]:
                self._situation_outcomes[situation][action_key] = {
                    "times_used": 0,
                    "wins": 0,
                    "avg_hp_change": 0,
                    "avg_damage_dealt": 0
                }
            
            outcome = self._situation_outcomes[situation][action_key]
            outcome["times_used"] += 1
            if won:
                outcome["wins"] += 1
            
            # Calculate HP changes and damage dealt
            if i < len(self._game_history) - 1:
                hp_change = self._game_history[i + 1]["hp_before"] - record["hp_before"]
                damage_dealt = record["opp_hp_before"] - self._game_history[i + 1]["opp_hp_before"]
                
                # Update running averages
                n = outcome["times_used"]
                outcome["avg_hp_change"] = ((n - 1) * outcome["avg_hp_change"] + hp_change) / n
                outcome["avg_damage_dealt"] = ((n - 1) * outcome["avg_damage_dealt"] + damage_dealt) / n
        
        # Adjust strategy weights based on performance
        learning_rate = 0.1
        if win_rate > 0.6:  # Winning strategy
            # Reinforce current weights slightly
            pass
        elif win_rate < 0.4:  # Losing strategy
            # Adjust weights to try different approach
            if self._stats["games_played"] % 5 == 0:  # Every 5 games
                self._strategy_weights["aggression"] *= (1 + random.uniform(-0.2, 0.2))
                self._strategy_weights["defense"] *= (1 + random.uniform(-0.2, 0.2))
                self._strategy_weights["resource_priority"] *= (1 + random.uniform(-0.2, 0.2))
        
        # Clear game history for next game
        self._game_history = []
        
        # Save learning data
        self._save_learning_data()

    def _serialize_action(self, action):
        """Convert action to hashable string"""
        move_str = f"move_{action['move'][0]}_{action['move'][1]}"
        if action['spell']:
            spell_str = f"spell_{action['spell']['name']}"
        else:
            spell_str = "spell_none"
        return f"{move_str}_{spell_str}"

    def _get_learned_priority(self, situation, action, base_priority):
        """Adjust priority based on learned outcomes"""
        action_key = self._serialize_action(action)
        
        if situation in self._situation_outcomes:
            if action_key in self._situation_outcomes[situation]:
                outcome = self._situation_outcomes[situation][action_key]
                
                # Calculate success rate
                if outcome["times_used"] > 0:
                    success_rate = outcome["wins"] / outcome["times_used"]
                    
                    # Adjust priority based on historical success
                    # More weight to decisions tried more times
                    confidence = min(outcome["times_used"] / 10, 1.0)
                    adjustment = (success_rate - 0.5) * 20 * confidence
                    
                    # Factor in average damage dealt and HP changes
                    adjustment += outcome["avg_damage_dealt"] * 0.5
                    adjustment += outcome["avg_hp_change"] * 0.3
                    
                    return base_priority + adjustment
        
        return base_priority

    def decide(self, state):
        self_data = state["self"]
        opp_data = state["opponent"]
        artifacts = state.get("artifacts", [])
        minions = state.get("minions", [])

        self_pos = self_data["position"]
        opp_pos = opp_data["position"]
        cooldowns = self_data["cooldowns"]
        mana = self_data["mana"]
        hp = self_data["hp"]

        def dist(a, b):
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

        def manhattan_dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        # Get current situation for learning
        current_situation = self._categorize_situation(state)

        # First round shield for early protection
        if self._first_round and cooldowns["shield"] == 0 and mana >= 20:
            self._first_round = False
            action = {"move": [0, 0], "spell": {"name": "shield"}}
            self._record_action(state, action)
            return action
        elif self._first_round:
            self._first_round = False

        # Generate all possible moves
        possible_moves = [[dx, dy] for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
        
        # Build comprehensive spell list with priorities
        spells = []

        # Build enemy list
        enemies = [e for e in minions if e["owner"] != self_data["name"]]
        enemies.append(opp_data)

        # Apply learned spell preferences
        spell_weights = self._strategy_weights["spell_preference"]

        # Melee attack
        adjacent_enemies = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]
        if cooldowns["melee_attack"] == 0 and adjacent_enemies:
            for enemy in adjacent_enemies:
                base_priority = (25 if enemy["hp"] <= 30 else 18) * spell_weights["melee_attack"]
                spells.append({
                    "name": "melee_attack",
                    "target": enemy["position"],
                    "priority": base_priority
                })

        # Fireball
        if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            base_priority = (22 if hp > 50 else 16) * spell_weights["fireball"] * self._strategy_weights["aggression"]
            spells.append({
                "name": "fireball",
                "target": opp_pos,
                "priority": base_priority
            })

        # Heal
        if cooldowns["heal"] == 0 and mana >= 25 and hp <= 80:
            if hp <= 40:
                base_priority = 30 * spell_weights["heal"] * self._strategy_weights["defense"]
            elif hp <= 60:
                base_priority = 20 * spell_weights["heal"] * self._strategy_weights["defense"]
            else:
                base_priority = 12 * spell_weights["heal"] * self._strategy_weights["defense"]
            spells.append({"name": "heal", "priority": base_priority})

        # Shield
        if cooldowns["shield"] == 0 and mana >= 20 and hp <= 70:
            base_priority = (24 if hp <= 40 else 14) * spell_weights["shield"] * self._strategy_weights["defense"]
            spells.append({"name": "shield", "priority": base_priority})

        # Summon minion
        if cooldowns["summon"] == 0 and mana >= 50:
            has_minion = any(m["owner"] == self_data["name"] for m in minions)
            if not has_minion:
                base_priority = (10 if mana > 80 else 6) * spell_weights["summon"]
                spells.append({"name": "summon", "priority": base_priority})

        # Teleport to artifacts
        if cooldowns["teleport"] == 0 and mana >= 40 and artifacts:
            critical = mana <= 40 or hp <= 60
            if critical:
                for artifact in artifacts[:2]:
                    base_priority = 19 * spell_weights["teleport"] * self._strategy_weights["resource_priority"]
                    spells.append({
                        "name": "teleport",
                        "target": artifact["position"],
                        "priority": base_priority
                    })
            elif mana < 70 or hp < 80:
                for artifact in artifacts[:1]:
                    base_priority = 8 * spell_weights["teleport"] * self._strategy_weights["resource_priority"]
                    spells.append({
                        "name": "teleport",
                        "target": artifact["position"],
                        "priority": base_priority
                    })

        # No spell option
        spells.append({"name": None, "priority": 0})

        # Advanced evaluation function with learning
        def evaluate(move, spell_data):
            new_pos = [
                max(0, min(19, self_pos[0] + max(-1, min(1, move[0])))),
                max(0, min(19, self_pos[1] + max(-1, min(1, move[1]))))
            ]
            
            # Base score
            score = hp * 2.0 + mana * 1.0
            
            # Apply learned priority adjustment
            temp_action = {"move": move, "spell": spell_data if spell_data["name"] else None}
            adjusted_priority = self._get_learned_priority(
                current_situation,
                temp_action,
                spell_data.get("priority", 0)
            )
            score += adjusted_priority * 6
            
            # Positional scoring with learned weights
            aggression_weight = self._strategy_weights["aggression"]
            defense_weight = self._strategy_weights["defense"]
            resource_weight = self._strategy_weights["resource_priority"]
            positioning_weight = self._strategy_weights["positioning"]
            
            if hp > 70 and mana > 60:
                score += (12 - dist(new_pos, opp_pos)) * 2.5 * aggression_weight
            elif hp <= 40 or mana <= 30:
                score += dist(new_pos, opp_pos) * 2.0 * defense_weight
                if artifacts:
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (12 - dist(new_pos, nearest_artifact["position"])) * 4 * resource_weight
            elif hp <= 60 or mana <= 50:
                score += dist(new_pos, opp_pos) * 0.5 * defense_weight
                if artifacts:
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (10 - dist(new_pos, nearest_artifact["position"])) * 3 * resource_weight
            else:
                score += (10 - dist(new_pos, opp_pos)) * 1.5 * aggression_weight
                if artifacts and (mana < 70 or hp < 80):
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (9 - dist(new_pos, nearest_artifact["position"])) * 2 * resource_weight

            # Center control
            center = [9, 9]
            center_bonus = (15 - dist(new_pos, center)) * 0.8 * positioning_weight
            score += center_bonus
            
            # Avoid corners
            if (new_pos[0] <= 1 or new_pos[0] >= 18) and (new_pos[1] <= 1 or new_pos[1] >= 18):
                score -= 10
            
            # Optimal distance bonus
            opp_distance = dist(new_pos, opp_pos)
            if 3 <= opp_distance <= 5:
                score += 5 * positioning_weight
            
            return score

        # Evaluate all combinations
        best_score = float('-inf')
        best_move = [0, 0]
        best_spell = None

        for move in possible_moves:
            for spell_data in spells:
                score = evaluate(move, spell_data)
                score += random.uniform(0, 0.5)
                
                if score > best_score:
                    best_score = score
                    best_move = move
                    if spell_data["name"]:
                        if "target" in spell_data:
                            best_spell = {
                                "name": spell_data["name"],
                                "target": spell_data["target"]
                            }
                        else:
                            best_spell = {"name": spell_data["name"]}
                    else:
                        best_spell = None

        action = {
            "move": best_move,
            "spell": best_spell
        }
        
        # Record action for learning
        self._record_action(state, action)
        
        return action

    def game_over(self, won):
        """Called when game ends - learn from the outcome"""
        self._learn_from_game(won)