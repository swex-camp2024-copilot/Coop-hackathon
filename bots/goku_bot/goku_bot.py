import random

from bots.bot_interface import BotInterface


class CustomBot (BotInterface):
    def __init__(self):
        # Adding these properties makes the interface clearer
        self._name = "Goku Bot"
        self._sprite_path = "assets/wizards/chibi-goku.png"
        self._minion_sprite_path = "assets/minions/saibaman.webp"

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

        # Generate all possible moves (stay, or move -1/0/1 in each direction)
        possible_moves = [[dx, dy] for dx in [-1, 0, 1] for dy in [-1, 0, 1]
                          if not (dx == 0 and dy == 0) or True]  # allow staying in place

        # Generate all possible spells
        spells = []
        # Melee attack if adjacent
        enemies = [e for e in minions if e["owner"] != self_data["name"]]
        enemies.append(opp_data)
        adjacent_enemies = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]
        if cooldowns["melee_attack"] == 0 and adjacent_enemies:
            for enemy in adjacent_enemies:
                spells.append({"name": "melee_attack", "target": enemy["position"]})
        # Fireball
        if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            spells.append({"name": "fireball", "target": opp_pos})
        # Shield
        if cooldowns["shield"] == 0 and mana >= 20 and hp <= 60:
            spells.append({"name": "shield"})
        # Heal
        if cooldowns["heal"] == 0 and mana >= 25 and hp <= 80:
            spells.append({"name": "heal"})
        # Summon
        if cooldowns["summon"] == 0 and mana >= 50 and not any(m["owner"] == self_data["name"] for m in minions):
            spells.append({"name": "summon"})
        # Teleport to artifact
        if cooldowns["teleport"] == 0 and mana >= 40 and artifacts:
            for artifact in artifacts:
                spells.append({"name": "teleport", "target": artifact["position"]})
        # No spell (just move)
        spells.append(None)

        # Evaluation function for a state after action
        def evaluate(move, spell):
            # Estimate new position (limit to one step)
            new_pos = [self_pos[0] + max(-1, min(1, move[0])), self_pos[1] + max(-1, min(1, move[1]))]
            # Score: prefer higher HP, mana, being close to artifacts if low, and attacking if possible
            score = hp + 0.5 * mana
            # Prefer being closer to opponent if healthy, farther if low HP
            if hp > 50:
                score += 10 - dist(new_pos, opp_pos)
            else:
                score += dist(new_pos, opp_pos)
            # Prefer being close to artifact if low on mana/hp
            if artifacts and (mana < 60 or hp < 60):
                nearest = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                score += 5 - dist(new_pos, nearest["position"])
            # Prefer attacking spells
            if spell:
                if spell["name"] == "melee_attack":
                    score += 15
                elif spell["name"] == "fireball":
                    score += 12
                elif spell["name"] == "heal":
                    score += 8
                elif spell["name"] == "shield":
                    score += 6
                elif spell["name"] == "summon":
                    score += 5
                elif spell["name"] == "teleport":
                    score += 4
            return score

        # Try all move/spell combinations and pick the best
        best_score = float('-inf')
        best_move = [0, 0]
        best_spell = None
        for move in possible_moves:
            for spell in spells:
                score = evaluate(move, spell)
                if score > best_score:
                    best_score = score
                    best_move = move
                    best_spell = spell

        return {
            "move": best_move,
            "spell": best_spell
        }

    def move_toward(self, start, target):
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        step_x = 1 if dx > 0 else -1 if dx < 0 else 0
        step_y = 1 if dy > 0 else -1 if dy < 0 else 0
        return [step_x, step_y]
