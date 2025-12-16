from bots.bot_interface import BotInterface

class ZeusSmartBot(BotInterface):
    def __init__(self):
        self._name = "Zeus"
        self._sprite_path = "assets/wizards/zeus.jpg"
        self._minion_sprite_path = "assets/minions/ares.jpg"
        self._first_turn = True  # Track first turn for smart teleport

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

        move = [0, 0]
        spell = None

        def dist(a, b):
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

        def manhattan_dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        enemies = [e for e in minions if e["owner"] != self_data["name"]] + [opp_data]
        adjacent_enemies = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]

        # FIRST TURN: Smart Teleport toward artifact closer to opponent or strategic position
        if self._first_turn:
            self._first_turn = False
            if cooldowns.get("teleport", 0) == 0 and mana >= 40 and artifacts:
                # pick closest artifact that also moves toward opponent
                target_art = min(artifacts, key=lambda a: dist(a["position"], opp_pos))
                spell = {"name": "teleport", "target": target_art["position"]}
                return {"move": move, "spell": spell}

        # Reactively cast shield if low HP or expecting damage
        if hp <= 50 and cooldowns.get("shield", 0) == 0 and mana >= 20:
            spell = {"name": "shield"}

        # Summon minion early if none exists
        elif cooldowns.get("summon", 0) == 0 and mana >= 50:
            has_minion = any(m["owner"] == self_data["name"] for m in minions)
            if not has_minion:
                spell = {"name": "summon"}

        # Heal if HP moderately low
        elif hp <= 80 and cooldowns.get("heal", 0) == 0 and mana >= 25:
            spell = {"name": "heal"}

        # Melee attack if adjacent
        elif adjacent_enemies and cooldowns.get("melee_attack", 0) == 0:
            target = min(adjacent_enemies, key=lambda e: e["hp"])
            spell = {"name": "melee_attack", "target": target["position"]}

        # Fireball if in range
        elif cooldowns.get("fireball", 0) == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            spell = {"name": "fireball", "target": opp_pos}

        # Move toward useful artifact if HP or mana low
        if not spell and artifacts and (mana <= 60 or hp <= 60):
            nearest = min(artifacts, key=lambda a: dist(self_pos, a["position"]))
            move = self.move_toward(self_pos, nearest["position"])
        # Otherwise, move toward opponent
        elif not spell:
            move = self.move_toward(self_pos, opp_pos)

        return {"move": move, "spell": spell}

    def move_toward(self, start, target):
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        step_x = 1 if dx > 0 else -1 if dx < 0 else 0
        step_y = 1 if dy > 0 else -1 if dy < 0 else 0
        return [step_x, step_y]
