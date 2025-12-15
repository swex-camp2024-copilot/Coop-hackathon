import random
import json
import os

from bots.bot_interface import BotInterface


class EnhancedBot(BotInterface):
    def __init__(self):
        self._name = "Enhanced Persistent Self Learning Bot"
        self._sprite_path = "assets/wizards/coop-rg-2-bot.png"
        self._minion_sprite_path = "assets/minions/minion-rg-2.png"
        self._first_round = True
        self._kill_mode = False
        
        # LEARNING SYSTEM
        self._memory_file = "bots/enhanced_persistent_self_learning_bot/opponent_memory.json"
        self._opponent_memory = self._load_memory()
        self._current_opponent = None
        self._turn_count = 0
        self._last_state = None
        self._last_opp_hp = 100
        self._last_opp_mana = 100
        self._last_opp_pos = None
        
        # Pattern tracking for current match
        self._opponent_patterns = {
            "aggression_level": 0.5,  # 0=defensive, 1=aggressive
            "spell_usage": {},
            "movement_tendency": 0.5,  # 0=retreat, 1=chase
            "artifact_priority": 0.5,  # 0=low, 1=high
            "healing_threshold": 50,
            "shield_threshold": 50,
            "fireball_frequency": 0,
            "melee_frequency": 0,
            "teleport_usage": 0
        }

    @property
    def name(self):
        return self._name

    @property
    def sprite_path(self):
        return self._sprite_path

    @property
    def minion_sprite_path(self):
        return self._minion_sprite_path

    def _load_memory(self):
        """Load opponent memory from file"""
        if os.path.exists(self._memory_file):
            try:
                with open(self._memory_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_memory(self):
        """Save opponent memory to file"""
        try:
            os.makedirs(os.path.dirname(self._memory_file), exist_ok=True)
            with open(self._memory_file, 'w') as f:
                json.dump(self._opponent_memory, f, indent=2)
        except:
            pass

    def _update_opponent_memory(self, opponent_name, pattern_data):
        """Update long-term memory about opponent"""
        if opponent_name not in self._opponent_memory:
            self._opponent_memory[opponent_name] = {
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "average_aggression": 0.5,
                "common_strategies": [],
                "weaknesses": [],
                "spell_preferences": {},
                "average_healing_threshold": 50,
                "average_shield_threshold": 50
            }
        
        memory = self._opponent_memory[opponent_name]
        memory["matches_played"] += 1
        
        # Update with exponential moving average
        alpha = 0.3  # Learning rate
        memory["average_aggression"] = (1 - alpha) * memory["average_aggression"] + alpha * pattern_data["aggression_level"]
        memory["average_healing_threshold"] = (1 - alpha) * memory["average_healing_threshold"] + alpha * pattern_data["healing_threshold"]
        memory["average_shield_threshold"] = (1 - alpha) * memory["average_shield_threshold"] + alpha * pattern_data["shield_threshold"]
        
        # Update spell preferences
        for spell, freq in pattern_data["spell_usage"].items():
            if spell not in memory["spell_preferences"]:
                memory["spell_preferences"][spell] = 0
            memory["spell_preferences"][spell] = (1 - alpha) * memory["spell_preferences"][spell] + alpha * freq
        
        self._save_memory()

    def _analyze_opponent_behavior(self, state):
        """Analyze opponent's current behavior and learn patterns"""
        opp_data = state["opponent"]
        opp_pos = opp_data["position"]
        opp_hp = opp_data["hp"]
        opp_mana = opp_data.get("mana", 100)
        
        if self._current_opponent is None:
            self._current_opponent = opp_data["name"]
            # Load historical data if available
            if self._current_opponent in self._opponent_memory:
                memory = self._opponent_memory[self._current_opponent]
                self._opponent_patterns["aggression_level"] = memory["average_aggression"]
                self._opponent_patterns["healing_threshold"] = memory["average_healing_threshold"]
                self._opponent_patterns["shield_threshold"] = memory["average_shield_threshold"]
        
        if self._last_state is not None:
            self_pos = state["self"]["position"]
            last_self_pos = self._last_state["self"]["position"]
            
            # Track movement tendency
            last_dist = max(abs(last_self_pos[0] - self._last_opp_pos[0]), 
                           abs(last_self_pos[1] - self._last_opp_pos[1]))
            current_dist = max(abs(self_pos[0] - opp_pos[0]), 
                              abs(self_pos[1] - opp_pos[1]))
            
            if current_dist < last_dist:
                self._opponent_patterns["movement_tendency"] = min(1.0, self._opponent_patterns["movement_tendency"] + 0.05)
            elif current_dist > last_dist:
                self._opponent_patterns["movement_tendency"] = max(0.0, self._opponent_patterns["movement_tendency"] - 0.05)
            
            # Track spell usage
            hp_damage = self._last_opp_hp - opp_hp
            if hp_damage > 0:
                # Took damage - track what they did
                if hp_damage >= 25:  # Likely fireball
                    self._opponent_patterns["fireball_frequency"] += 1
                    self._opponent_patterns["spell_usage"]["fireball"] = self._opponent_patterns.get("spell_usage", {}).get("fireball", 0) + 1
                elif hp_damage >= 15:  # Likely melee
                    self._opponent_patterns["melee_frequency"] += 1
                    self._opponent_patterns["spell_usage"]["melee"] = self._opponent_patterns.get("spell_usage", {}).get("melee", 0) + 1
            
            # Track healing behavior
            opp_hp_change = opp_hp - self._last_opp_hp
            if opp_hp_change > 20:  # They healed
                self._opponent_patterns["healing_threshold"] = max(self._opponent_patterns["healing_threshold"], self._last_opp_hp)
                self._opponent_patterns["spell_usage"]["heal"] = self._opponent_patterns.get("spell_usage", {}).get("heal", 0) + 1
            
            # Track mana usage
            mana_spent = self._last_opp_mana - opp_mana
            if mana_spent >= 40:  # Teleport
                self._opponent_patterns["teleport_usage"] += 1
                self._opponent_patterns["spell_usage"]["teleport"] = self._opponent_patterns.get("spell_usage", {}).get("teleport", 0) + 1
            
            # Calculate aggression level
            total_spells = sum(self._opponent_patterns["spell_usage"].values()) or 1
            offensive_spells = self._opponent_patterns["spell_usage"].get("fireball", 0) + self._opponent_patterns["spell_usage"].get("melee", 0)
            self._opponent_patterns["aggression_level"] = offensive_spells / total_spells
        
        self._last_state = state
        self._last_opp_hp = opp_hp
        self._last_opp_mana = opp_mana
        self._last_opp_pos = opp_pos
        self._turn_count += 1

    def _predict_opponent_action(self, state):
        """Predict what opponent will do based on learned patterns"""
        opp_data = state["opponent"]
        opp_hp = opp_data["hp"]
        opp_mana = opp_data.get("mana", 100)
        opp_pos = opp_data["position"]
        self_pos = state["self"]["position"]
        
        predictions = {
            "will_heal": False,
            "will_shield": False,
            "will_fireball": False,
            "will_melee": False,
            "will_chase": False,
            "will_retreat": False,
            "danger_level": 0  # 0-10
        }
        
        # Predict healing
        if opp_hp <= self._opponent_patterns["healing_threshold"] and opp_mana >= 25:
            predictions["will_heal"] = True
            predictions["danger_level"] -= 2
        
        # Predict shielding
        if opp_hp <= self._opponent_patterns["shield_threshold"] and opp_mana >= 20:
            predictions["will_shield"] = True
        
        # Predict fireball
        current_dist = max(abs(self_pos[0] - opp_pos[0]), abs(self_pos[1] - opp_pos[1]))
        if current_dist <= 5 and opp_mana >= 30:
            fireball_chance = self._opponent_patterns["aggression_level"]
            if fireball_chance > 0.5:
                predictions["will_fireball"] = True
                predictions["danger_level"] += 5
        
        # Predict melee
        if current_dist == 1:
            predictions["will_melee"] = True
            predictions["danger_level"] += 3
        
        # Predict movement
        if self._opponent_patterns["movement_tendency"] > 0.6:
            predictions["will_chase"] = True
            predictions["danger_level"] += 2
        elif self._opponent_patterns["movement_tendency"] < 0.4:
            predictions["will_retreat"] = True
            predictions["danger_level"] -= 3
        
        return predictions

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
        opp_hp = opp_data["hp"]
        opp_mana = opp_data.get("mana", 100)

        # LEARN from opponent behavior
        self._analyze_opponent_behavior(state)
        predictions = self._predict_opponent_action(state)

        def dist(a, b):
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))  # Chebyshev

        def manhattan_dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        # Calculate potential damage we can deal
        def calculate_kill_potential():
            damage = 0
            attacks = []
            
            if cooldowns["melee_attack"] == 0 and manhattan_dist(self_pos, opp_pos) == 1:
                damage += 20
                attacks.append("melee")
            
            if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
                damage += 30
                attacks.append("fireball")
            
            can_move_to_melee = dist(self_pos, opp_pos) <= 2
            if cooldowns["melee_attack"] == 0 and can_move_to_melee and "melee" not in attacks:
                damage += 20
            
            return damage, attacks

        potential_damage, available_attacks = calculate_kill_potential()
        self._kill_mode = opp_hp <= potential_damage and len(available_attacks) > 0

        # ADAPTIVE: Adjust kill mode based on predictions
        if predictions["will_heal"] and opp_hp <= 60:
            # Strike before they heal
            self._kill_mode = True
        
        if predictions["will_shield"] and predictions["danger_level"] < 3:
            # Their shield won't save them, go aggressive
            potential_damage += 10  # Account for reduced damage

        # FROM BOT 2: First round shield UNLESS opponent is very aggressive
        if self._first_round:
            self._first_round = False
            # Skip first shield if opponent historically very aggressive
            if self._opponent_patterns["aggression_level"] < 0.7 and cooldowns["shield"] == 0 and mana >= 20:
                return {"move": [0, 0], "spell": {"name": "shield"}}

        possible_moves = [[dx, dy] for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
        spells = []

        # Build enemy list
        enemies = [e for e in minions if e["owner"] != self_data["name"]]
        enemy_minions = enemies.copy()
        enemies.append(opp_data)

        my_minions = [m for m in minions if m["owner"] == self_data["name"]]
        threat_count = len(enemy_minions) + 1

        # MELEE ATTACK - ADAPTIVE
        adjacent_enemies = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]
        if cooldowns["melee_attack"] == 0 and adjacent_enemies:
            for enemy in adjacent_enemies:
                if enemy == opp_data:
                    if opp_hp <= 20:
                        priority = 50
                    elif opp_hp <= 40:
                        priority = 35
                    elif self._kill_mode:
                        priority = 40
                    elif predictions["will_retreat"]:
                        # They're running, capitalize
                        priority = 30
                    else:
                        priority = 25
                else:
                    if enemy["hp"] <= 20:
                        priority = 30
                    else:
                        priority = 18
                
                spells.append({"name": "melee_attack", "target": enemy["position"], "priority": priority})

        # FIREBALL - ADAPTIVE TO OPPONENT PATTERNS
        if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            if opp_hp <= 30:
                priority = 48
            elif opp_hp <= 50:
                priority = 38
            elif predictions["will_heal"]:
                # Punish healing attempts
                priority = 36
            elif opp_hp <= 70:
                priority = 30
            elif self._kill_mode:
                priority = 42
            elif predictions["will_chase"] and mana > 60:
                # They're aggressive, trade damage
                priority = 28
            elif mana > 60 and hp > 50:
                priority = 26
            else:
                priority = 22
            
            spells.append({"name": "fireball", "target": opp_pos, "priority": priority})

        # SHIELD - ADAPTIVE TO THREAT LEVEL
        if cooldowns["shield"] == 0 and mana >= 20 and not self._kill_mode:
            threat_multiplier = 1 + (predictions["danger_level"] / 10)
            
            if hp <= 40:
                priority = int(32 * threat_multiplier)
            elif hp <= 60 and predictions["will_fireball"]:
                priority = int(30 * threat_multiplier)
            elif hp <= 75:
                priority = int(18 * threat_multiplier)
            elif predictions["danger_level"] >= 6:
                # High danger, shield preemptively
                priority = 24
            else:
                priority = 10
            
            spells.append({"name": "shield", "priority": priority})

        # HEAL - ADAPTIVE TO OPPONENT HEALING PATTERNS
        if cooldowns["heal"] == 0 and mana >= 25 and not self._kill_mode:
            # Heal earlier if opponent is aggressive
            aggression_modifier = -10 if self._opponent_patterns["aggression_level"] > 0.7 else 0
            
            if hp <= 25:
                priority = 45
            elif hp <= 40:
                priority = 30
            elif hp <= 60:
                priority = 20 - aggression_modifier
            elif hp <= 75:
                priority = 12 - aggression_modifier
            else:
                priority = 0
            
            if priority > 0:
                spells.append({"name": "heal", "priority": priority})

        # SUMMON - ADAPTIVE
        if cooldowns["summon"] == 0 and mana >= 50 and not self._kill_mode:
            has_minion = any(m["owner"] == self_data["name"] for m in minions)
            if not has_minion:
                if threat_count > len(my_minions) + 1:
                    priority = 20
                elif self._opponent_patterns["aggression_level"] > 0.6:
                    # Opponent is aggressive, summon for defense
                    priority = 18
                elif mana > 80:
                    priority = 16
                elif hp > 70:
                    priority = 14
                else:
                    priority = 10
                
                spells.append({"name": "summon", "priority": priority})

        # TELEPORT - ADAPTIVE
        if cooldowns["teleport"] == 0 and mana >= 40 and artifacts:
            if hp <= 30 and opp_hp > 50:
                for artifact in artifacts[:2]:
                    if dist(artifact["position"], opp_pos) > dist(self_pos, opp_pos):
                        priority = 35
                        spells.append({"name": "teleport", "target": artifact["position"], "priority": priority})
            elif mana <= 40 or (opp_hp <= 40 and mana < 60):
                for artifact in artifacts[:2]:
                    priority = 24
                    spells.append({"name": "teleport", "target": artifact["position"], "priority": priority})
            elif dist(self_pos, opp_pos) > 7 and opp_hp < hp and not predictions["will_retreat"]:
                for artifact in artifacts[:1]:
                    if dist(artifact["position"], opp_pos) < dist(self_pos, opp_pos):
                        priority = 18
                        spells.append({"name": "teleport", "target": artifact["position"], "priority": priority})

        spells.append({"name": None, "priority": 0})

        # ADAPTIVE EVALUATION FUNCTION
        def evaluate(move, spell_data):
            new_pos = [
                max(0, min(19, self_pos[0] + max(-1, min(1, move[0])))),
                max(0, min(19, self_pos[1] + max(-1, min(1, move[1]))))
            ]
            
            score = hp * 2.0 + mana * 1.5
            
            if spell_data["name"]:
                priority = spell_data.get("priority", 0)
                if priority >= 45:
                    score += priority * 15
                elif priority >= 35:
                    score += priority * 12
                else:
                    score += priority * 7
            
            hp_advantage = hp - opp_hp
            new_dist = dist(new_pos, opp_pos)
            
            # ADAPTIVE AGGRESSION based on opponent patterns
            aggression_factor = 1.0
            if self._opponent_patterns["aggression_level"] > 0.7:
                # Opponent is aggressive, be more cautious
                aggression_factor = 0.8
            elif self._opponent_patterns["aggression_level"] < 0.3:
                # Opponent is passive, be more aggressive
                aggression_factor = 1.3
            
            if self._kill_mode or opp_hp <= 50:
                score += (15 - new_dist) * 5 * aggression_factor
                
                if new_dist <= 5 and mana >= 30:
                    score += 30
                if manhattan_dist(new_pos, opp_pos) <= 1:
                    score += 25
                
                if new_dist > dist(self_pos, opp_pos):
                    score -= 20
            
            elif hp > 70 and hp_advantage > 15:
                score += (12 - new_dist) * 3.5 * aggression_factor
                
                if new_dist >= 3 and new_dist <= 5:
                    score += 25
            
            elif hp <= 40 or hp_advantage < -15:
                score += new_dist * 4
                
                if artifacts:
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (12 - dist(new_pos, nearest_artifact["position"])) * 6
                
                if new_pos[0] <= 2 or new_pos[0] >= 17 or new_pos[1] <= 2 or new_pos[1] >= 17:
                    score -= 15
            
            else:
                optimal_range = 4
                # Adjust optimal range based on opponent behavior
                if predictions["will_chase"]:
                    optimal_range = 5  # Stay a bit further
                elif predictions["will_retreat"]:
                    optimal_range = 3  # Close in
                
                range_diff = abs(new_dist - optimal_range)
                score += (8 - range_diff) * 2
                
                if artifacts and (mana < 60 or hp < 70):
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (10 - dist(new_pos, nearest_artifact["position"])) * 3
            
            # ADAPTIVE PENALTIES
            # Adjust melee penalty based on opponent melee frequency
            if hp <= 50 and manhattan_dist(new_pos, opp_pos) == 1 and not self._kill_mode:
                melee_danger = 30 + (self._opponent_patterns["melee_frequency"] * 5)
                score -= melee_danger
            
            if new_pos[0] == 0 or new_pos[0] == 19 or new_pos[1] == 0 or new_pos[1] == 19:
                score -= 12
            
            center = [9, 9]
            score += (15 - dist(new_pos, center)) * 0.5
            
            if artifacts:
                for artifact in artifacts[:2]:
                    if dist(new_pos, artifact["position"]) < dist(opp_pos, artifact["position"]):
                        if dist(new_pos, opp_pos) <= 6:
                            score += 8
            
            # PREDICTION-BASED BONUSES
            if predictions["will_fireball"] and new_dist > 5:
                score += 15  # Bonus for getting out of range
            
            if predictions["will_heal"] and new_dist <= 5 and mana >= 30:
                score += 20  # Bonus for being in position to punish heal
            
            return score

        # Evaluate all combinations
        best_score = float('-inf')
        best_move = [0, 0]
        best_spell = None

        for move in possible_moves:
            for spell_data in spells:
                score = evaluate(move, spell_data)
                if score > best_score:
                    best_score = score
                    best_move = move
                    best_spell = spell_data["name"] if spell_data["name"] else None
                    if best_spell and "target" in spell_data:
                        best_spell = {"name": spell_data["name"], "target": spell_data["target"]}
                    elif best_spell:
                        best_spell = {"name": spell_data["name"]}

        # Update memory at end of match (when HP drops to 0)
        if hp <= 0 or opp_hp <= 0:
            self._update_opponent_memory(self._current_opponent, self._opponent_patterns)
            if opp_hp <= 0:
                self._opponent_memory[self._current_opponent]["wins"] += 1
            else:
                self._opponent_memory[self._current_opponent]["losses"] += 1
            self._save_memory()

        return {
            "move": best_move,
            "spell": best_spell
        }