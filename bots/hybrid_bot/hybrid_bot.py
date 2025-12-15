import random

from bots.bot_interface import BotInterface


class EnhancedBot(BotInterface):
    def __init__(self):
        self._name = "Hybrid Bot"
        self._sprite_path = "assets/wizards/coop-rg-2-bot.png"
        self._minion_sprite_path = "assets/minions/minion-rg-2.png"
        self._first_round = True

    @property
    def name(self):
        return self._name

    @property
    def sprite_path(self):
        return self._sprite_path

    @property
    def minion_sprite_path(self):
        return self._minion_sprite_path

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
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))  # Chebyshev

        def manhattan_dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        # FROM BOT 2: First round shield for early protection
        if self._first_round and cooldowns["shield"] == 0 and mana >= 20:
            self._first_round = False
            return {"move": [0, 0], "spell": {"name": "shield"}}
        elif self._first_round:
            self._first_round = False

        # FROM GOKU BOT: Evaluate all possible actions
        possible_moves = [[dx, dy] for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
        spells = []

        # Build enemy list
        enemies = [e for e in minions if e["owner"] != self_data["name"]]
        enemies.append(opp_data)

        # Melee attack options
        adjacent_enemies = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]
        if cooldowns["melee_attack"] == 0 and adjacent_enemies:
            for enemy in adjacent_enemies:
                spells.append({"name": "melee_attack", "target": enemy["position"], "priority": 15})

        # Fireball (prioritize when opponent is in range)
        if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            spells.append({"name": "fireball", "target": opp_pos, "priority": 20})

        # Shield (Bot 3's higher threshold of 70 for more aggressive play)
        if cooldowns["shield"] == 0 and mana >= 20 and hp <= 70:
            spells.append({"name": "shield", "priority": 12})

        # Heal (Bot 2's conservative threshold)
        if cooldowns["heal"] == 0 and mana >= 25 and hp <= 80:
            # Higher priority if very low HP
            priority = 18 if hp <= 40 else 10
            spells.append({"name": "heal", "priority": priority})

        # Summon minion
        if cooldowns["summon"] == 0 and mana >= 50:
            has_minion = any(m["owner"] == self_data["name"] for m in minions)
            if not has_minion:
                spells.append({"name": "summon", "priority": 8})

        # Teleport to artifacts (Bot 2's critical resource management)
        if cooldowns["teleport"] == 0 and mana >= 40 and artifacts:
            critical = mana <= 40 or hp <= 60
            if critical:
                for artifact in artifacts[:2]:  # Consider top 2 nearest
                    spells.append({"name": "teleport", "target": artifact["position"], "priority": 14})

        # No spell option
        spells.append({"name": None, "priority": 0})

        # FROM GOKU BOT: Enhanced evaluation function
        def evaluate(move, spell_data):
            new_pos = [
                max(0, min(19, self_pos[0] + max(-1, min(1, move[0])))),
                max(0, min(19, self_pos[1] + max(-1, min(1, move[1]))))
            ]
            
            # Base score from HP and mana
            score = hp * 1.5 + mana * 0.8
            
            # Spell priority bonus
            if spell_data["name"]:
                score += spell_data.get("priority", 0) * 5
            
            # Positional scoring
            if hp > 60 and mana > 50:
                # Aggressive: close to opponent
                score += (10 - dist(new_pos, opp_pos)) * 2
            elif hp <= 40 or mana <= 30:
                # Defensive: maintain distance, get artifacts
                score += dist(new_pos, opp_pos) * 1.5
                if artifacts:
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (10 - dist(new_pos, nearest_artifact["position"])) * 3
            else:
                # Balanced: moderate aggression with artifact awareness
                score += (8 - dist(new_pos, opp_pos))
                if artifacts and (mana < 60 or hp < 70):
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (8 - dist(new_pos, nearest_artifact["position"])) * 2
            
            # Bonus for staying near center (better positioning)
            center = [9, 9]
            score += (10 - dist(new_pos, center)) * 0.5
            
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

        return {
            "move": best_move,
            "spell": best_spell
        }