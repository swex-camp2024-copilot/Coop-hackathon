import random
import json
import os

from bots.bot_interface import BotInterface


class EnhancedBot(BotInterface):
    def __init__(self):
        self._name = "Enhanced Faster Self Learning Bot"
        self._sprite_path = "assets/wizards/coop-rg-2-bot.png"
        self._minion_sprite_path = "assets/minions/minion-rg-2.png"
        self._first_round = True
        self._kill_mode = False
        
        # OPTIMIZED LEARNING SYSTEM
        self._memory_file = "bots/hybrid_bot/opponent_memory.json"
        self._opponent_memory = self._load_memory()
        self._current_opponent = None
        self._turn_count = 0
        self._last_opp_hp = 100
        self._last_opp_mana = 100
        self._last_opp_pos = None
        self._last_self_hp = 100
        
        # FAST pattern tracking - minimal state
        self._patterns = {
            "aggro": 0.5,  # Simplified aggression (0-1)
            "defensive": 0.5,  # Defensive tendency (0-1)
            "fireball_count": 0,
            "melee_count": 0,
            "heal_count": 0,
            "attacks_received": 0,
            "damage_dealt_to_us": 0
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
        """Load opponent memory - simplified"""
        if os.path.exists(self._memory_file):
            try:
                with open(self._memory_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_memory(self):
        """Save memory - async would be better but simplified here"""
        try:
            os.makedirs(os.path.dirname(self._memory_file), exist_ok=True)
            with open(self._memory_file, 'w') as f:
                json.dump(self._opponent_memory, f)
        except:
            pass

    def _quick_learn(self, state):
        """FAST learning - minimal calculations"""
        opp_data = state["opponent"]
        self_data = state["self"]
        opp_hp = opp_data["hp"]
        self_hp = self_data["hp"]
        
        # Initialize opponent tracking
        if self._current_opponent is None:
            self._current_opponent = opp_data["name"]
            # Load historical data ONCE
            if self._current_opponent in self._opponent_memory:
                mem = self._opponent_memory[self._current_opponent]
                self._patterns["aggro"] = mem.get("aggro", 0.5)
                self._patterns["defensive"] = mem.get("defensive", 0.5)
        
        # Quick damage tracking
        self_damage = self._last_self_hp - self_hp
        if self_damage > 0:
            self._patterns["attacks_received"] += 1
            self._patterns["damage_dealt_to_us"] += self_damage
            
            # Fast aggression update
            if self_damage >= 25:  # Fireball
                self._patterns["fireball_count"] += 1
                self._patterns["aggro"] = min(1.0, self._patterns["aggro"] + 0.1)
            elif self_damage >= 15:  # Melee
                self._patterns["melee_count"] += 1
                self._patterns["aggro"] = min(1.0, self._patterns["aggro"] + 0.08)
        
        # Quick healing detection
        opp_hp_gain = opp_hp - self._last_opp_hp
        if opp_hp_gain > 20:
            self._patterns["heal_count"] += 1
            self._patterns["defensive"] = min(1.0, self._patterns["defensive"] + 0.1)
        
        self._last_opp_hp = opp_hp
        self._last_self_hp = self_hp
        self._turn_count += 1

    def _fast_predict(self, state):
        """FAST prediction - simple rules"""
        opp_hp = state["opponent"]["hp"]
        opp_pos = state["opponent"]["position"]
        self_pos = state["self"]["position"]
        current_dist = max(abs(self_pos[0] - opp_pos[0]), abs(self_pos[1] - opp_pos[1]))
        
        # Simple danger calculation
        danger = 0
        if current_dist <= 5 and self._patterns["fireball_count"] > 2:
            danger += 6
        if current_dist == 1 and self._patterns["melee_count"] > 1:
            danger += 4
        if self._patterns["aggro"] > 0.7:
            danger += 3
        
        return {
            "danger": danger,
            "will_heal": opp_hp < 50 and self._patterns["heal_count"] > 0,
            "aggressive": self._patterns["aggro"] > 0.6
        }

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

        # FAST LEARNING
        self._quick_learn(state)
        pred = self._fast_predict(state)

        def dist(a, b):
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

        def manhattan_dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        # FAST kill detection
        can_kill = False
        if manhattan_dist(self_pos, opp_pos) == 1 and cooldowns["melee_attack"] == 0:
            can_kill = opp_hp <= 20
        if dist(self_pos, opp_pos) <= 5 and cooldowns["fireball"] == 0 and mana >= 30:
            can_kill = can_kill or opp_hp <= 30
        
        self._kill_mode = can_kill

        # ADAPTIVE first round
        if self._first_round:
            self._first_round = False
            if self._patterns["aggro"] < 0.7 and cooldowns["shield"] == 0 and mana >= 20:
                return {"move": [0, 0], "spell": {"name": "shield"}}

        # SIMPLIFIED spell list
        spells = []
        enemies = [e for e in minions if e["owner"] != self_data["name"]]
        enemies.append(opp_data)

        # MELEE - simplified priority
        adjacent = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]
        if cooldowns["melee_attack"] == 0 and adjacent:
            target = min(adjacent, key=lambda e: e["hp"])  # Fastest: lowest HP
            priority = 50 if target["hp"] <= 20 else 30 if target == opp_data else 20
            spells.append({"name": "melee_attack", "target": target["position"], "priority": priority})

        # FIREBALL - simplified priority
        if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            if opp_hp <= 30:
                priority = 48
            elif opp_hp <= 60:
                priority = 35
            elif pred["will_heal"]:
                priority = 36  # Punish healing
            else:
                priority = 25
            spells.append({"name": "fireball", "target": opp_pos, "priority": priority})

        # SHIELD - danger-based
        if cooldowns["shield"] == 0 and mana >= 20 and not self._kill_mode:
            if hp <= 40 or pred["danger"] >= 6:
                priority = 32
            elif hp <= 70:
                priority = 18
            else:
                priority = 0
            if priority > 0:
                spells.append({"name": "shield", "priority": priority})

        # HEAL - simplified
        if cooldowns["heal"] == 0 and mana >= 25 and not self._kill_mode:
            if hp <= 30:
                priority = 45
            elif hp <= 50:
                priority = 28
            elif hp <= 70 and pred["aggressive"]:
                priority = 20  # Heal earlier vs aggressive
            else:
                priority = 0
            if priority > 0:
                spells.append({"name": "heal", "priority": priority})

        # SUMMON - simplified
        if cooldowns["summon"] == 0 and mana >= 50:
            has_minion = any(m["owner"] == self_data["name"] for m in minions)
            if not has_minion and (mana > 70 or hp < 60):
                spells.append({"name": "summon", "priority": 15})

        # TELEPORT - simplified
        if cooldowns["teleport"] == 0 and mana >= 40 and artifacts:
            if (hp <= 40 and opp_hp > 50) or (mana <= 40):
                # Just teleport to nearest artifact
                nearest = min(artifacts, key=lambda a: dist(self_pos, a["position"]))
                spells.append({"name": "teleport", "target": nearest["position"], "priority": 25})

        spells.append({"name": None, "priority": 0})

        # SIMPLIFIED evaluation
        def evaluate(move, spell_data):
            new_pos = [
                max(0, min(19, self_pos[0] + max(-1, min(1, move[0])))),
                max(0, min(19, self_pos[1] + max(-1, min(1, move[1]))))
            ]
            
            # Simple scoring
            score = hp * 2.5 + mana * 1.2
            
            # Spell bonus
            if spell_data["name"]:
                priority = spell_data.get("priority", 0)
                score += priority * (12 if priority >= 40 else 8)
            
            new_dist = dist(new_pos, opp_pos)
            hp_diff = hp - opp_hp
            
            # FAST positioning logic
            if self._kill_mode or opp_hp <= 50:
                # Aggressive
                score += (12 - new_dist) * 4
                if new_dist <= 5:
                    score += 25
            elif hp <= 40 or hp_diff < -20:
                # Defensive
                score += new_dist * 3
                if artifacts:
                    nearest_art = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (10 - dist(new_pos, nearest_art["position"])) * 4
            else:
                # Balanced
                optimal = 4 + (1 if pred["aggressive"] else 0)
                score += (8 - abs(new_dist - optimal)) * 2
            
            # Simple penalties
            if hp < 50 and new_dist == 1 and not self._kill_mode:
                score -= 25
            if new_pos[0] == 0 or new_pos[0] == 19 or new_pos[1] == 0 or new_pos[1] == 19:
                score -= 10
            
            return score

        # FAST evaluation - reduced search space
        best_score = float('-inf')
        best_move = [0, 0]
        best_spell = None

        # Prioritize high-value spells first (early pruning)
        spells.sort(key=lambda s: s.get("priority", 0), reverse=True)
        
        # Only evaluate top 3 spells with all moves, rest with limited moves
        for spell_idx, spell_data in enumerate(spells[:3]):  # Top 3 spells
            moves = [[dx, dy] for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
            for move in moves:
                score = evaluate(move, spell_data)
                if score > best_score:
                    best_score = score
                    best_move = move
                    best_spell = spell_data["name"] if spell_data["name"] else None
                    if best_spell and "target" in spell_data:
                        best_spell = {"name": spell_data["name"], "target": spell_data["target"]}
                    elif best_spell:
                        best_spell = {"name": spell_data["name"]}

        # Quick check lower priority spells with limited moves
        for spell_data in spells[3:]:
            for move in [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]:  # Only cardinal + stay
                score = evaluate(move, spell_data)
                if score > best_score:
                    best_score = score
                    best_move = move
                    best_spell = spell_data["name"] if spell_data["name"] else None
                    if best_spell and "target" in spell_data:
                        best_spell = {"name": spell_data["name"], "target": spell_data["target"]}
                    elif best_spell:
                        best_spell = {"name": spell_data["name"]}

        # FAST memory update at match end
        if hp <= 0 or opp_hp <= 0:
            if self._current_opponent not in self._opponent_memory:
                self._opponent_memory[self._current_opponent] = {}
            
            mem = self._opponent_memory[self._current_opponent]
            mem["aggro"] = self._patterns["aggro"]
            mem["defensive"] = self._patterns["defensive"]
            mem["matches"] = mem.get("matches", 0) + 1
            if opp_hp <= 0:
                mem["wins"] = mem.get("wins", 0) + 1
            
            self._save_memory()

        return {
            "move": best_move,
            "spell": best_spell
        }