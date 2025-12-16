from typing import List, Dict, Any, Tuple, Optional
from collections import deque

from bots.bot_interface import BotInterface


class ArchmageBot(BotInterface):
    def __init__(self) -> None:
        self.name_ = "Archmage"
        self._first_turn = True
        self._turn_count = 0
        self._last_hp = 100

    @property
    def name(self) -> str:
        return self.name_

    def decide(self, state: Dict[str, Any]) -> Dict[str, Any]:
        me = state["self"]
        opp = state["opponent"]
        my_pos = tuple(me["position"])
        opp_pos = tuple(opp["position"])
        artifacts = state.get("artifacts", [])
        minions = state.get("minions", [])
        cooldowns = me.get("cooldowns", {})
        hp = me["hp"]
        mana = me["mana"]
        opp_hp = opp["hp"]
        dist = self.get_dist(my_pos, opp_pos)
        opp_shielded = opp.get("shield_active", False)
        my_shielded = me.get("shield_active", False)

        self._turn_count += 1
        damage_taken = max(0, self._last_hp - hp)
        self._last_hp = hp

        own_minions = [m for m in minions if m["owner"] == me.get("name", self.name_)]
        enemy_minions = [m for m in minions if m["owner"] != me.get("name", self.name_)]
        hp_advantage = hp - opp_hp

        # PRIORITY 0: FIRST-TURN SHIELD
        if self._first_turn:
            self._first_turn = False
            if self.can_cast("shield", me):
                return {"move": [0, 0], "spell": {"name": "shield"}}

        # PRIORITY 1: EMERGENCY SURVIVAL (HP <= 35)
        if hp <= 35:
            if not my_shielded and self.can_cast("shield", me):
                return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": {"name": "shield"}}
            if self.can_cast("heal", me):
                return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": {"name": "heal"}}
            if self.can_cast("teleport", me) and artifacts:
                health_arts = [a for a in artifacts if a["type"] == "health"]
                if health_arts:
                    best = min(health_arts, key=lambda a: self.get_dist(my_pos, tuple(a["position"])))
                    return {"move": [0, 0], "spell": {"name": "teleport", "target": best["position"]}}
            if dist <= 4 and self.can_cast("blink", me):
                blink_dir = self.get_blink_away(my_pos, opp_pos, state)
                return {"move": [0, 0], "spell": {"name": "blink", "target": blink_dir}}
            return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": None}

        # PRIORITY 2: KILL ENEMY MINION (adjacent, they deal 10 dmg/turn)
        for em in enemy_minions:
            em_pos = tuple(em["position"])
            if self.manhattan_dist(my_pos, em_pos) == 1 and cooldowns.get("melee_attack", 0) == 0:
                return {"move": [0, 0], "spell": {"name": "melee_attack", "target": list(em_pos)}}

        # PRIORITY 3: PROACTIVE SHIELD (HP <= 55 and enemy close, or taking damage)
        if not my_shielded and self.can_cast("shield", me):
            if (hp <= 55 and dist <= 5) or (damage_taken >= 15):
                return {"move": [0, 0], "spell": {"name": "shield"}}

        # PRIORITY 4: MELEE ATTACK OPPONENT (adjacent, free damage)
        if self.manhattan_dist(my_pos, opp_pos) == 1 and cooldowns.get("melee_attack", 0) == 0:
            return {"move": [0, 0], "spell": {"name": "melee_attack", "target": list(opp_pos)}}

        # PRIORITY 5: FIREBALL (in range - even if shielded when we have HP advantage)
        if dist <= 5 and self.can_cast("fireball", me):
            if not opp_shielded or hp_advantage >= 20:
                step = self.bfs_move(my_pos, opp_pos, state)
                return {"move": step, "spell": {"name": "fireball", "target": list(opp_pos)}}

        # PRIORITY 6: SUMMON MINION (no minion and enough mana)
        if len(own_minions) == 0 and self.can_cast("summon", me) and mana >= 60:
            summon_pos = self.get_summon_position(my_pos, opp_pos, minions, state)
            if summon_pos:
                return {"move": [0, 0], "spell": {"name": "summon", "target": summon_pos}}

        # PRIORITY 7: HEAL (when safe and need it, or to maintain HP advantage)
        if self.can_cast("heal", me):
            if (hp <= 65 and dist >= 4) or (hp <= 80 and hp_advantage >= 20 and dist >= 3):
                return {"move": [0, 0], "spell": {"name": "heal"}}

        # PRIORITY 8: RESOURCE COLLECTION
        target_pos: Optional[Tuple[int, int]] = None
        if hp <= 60:
            target_pos = self.find_best_artifact(my_pos, opp_pos, artifacts, "health")
        if not target_pos and mana <= 40:
            target_pos = self.find_best_artifact(my_pos, opp_pos, artifacts, "mana")
        if not target_pos and (hp <= 80 or mana <= 60):
            target_pos = self.find_best_artifact(my_pos, opp_pos, artifacts, None)

        if target_pos:
            art_dist = self.get_dist(my_pos, target_pos)
            if art_dist >= 5 and self.can_cast("teleport", me):
                return {"move": [0, 0], "spell": {"name": "teleport", "target": list(target_pos)}}
            if art_dist >= 3 and self.can_cast("blink", me):
                blink_dir = self.get_blink_toward(my_pos, target_pos, state)
                return {"move": [0, 0], "spell": {"name": "blink", "target": blink_dir}}
            move = self.bfs_move(my_pos, target_pos, state)
            return {"move": move, "spell": None}

        # PRIORITY 9: AGGRESSIVE HUNT (when HP advantage)
        if hp_advantage >= 25 and dist > 2:
            if self.can_cast("blink", me):
                blink_dir = self.get_blink_toward(my_pos, opp_pos, state)
                return {"move": [0, 0], "spell": {"name": "blink", "target": blink_dir}}
            return {"move": self.bfs_move(my_pos, opp_pos, state), "spell": None}

        # PRIORITY 10: HUNT OPPONENT (close gap for fireball)
        if dist > 5:
            if self.can_cast("blink", me):
                blink_dir = self.get_blink_toward(my_pos, opp_pos, state)
                return {"move": [0, 0], "spell": {"name": "blink", "target": blink_dir}}
            return {"move": self.bfs_move(my_pos, opp_pos, state), "spell": None}

        # PRIORITY 11: MAINTAIN OPTIMAL DISTANCE (4-5 for fireball range)
        optimal = 4 if hp_advantage >= 10 else 5
        if dist < optimal - 1:
            return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": None}
        elif dist > optimal + 1:
            return {"move": self.bfs_move(my_pos, opp_pos, state), "spell": None}

        # PRIORITY 12: AVOID EDGES (reposition toward center)
        if self.is_near_edge(my_pos, state):
            center = (4, 4)
            return {"move": self.bfs_move(my_pos, center, state), "spell": None}

        return {"move": [0, 0], "spell": None}

    # --- HELPERS ---

    def can_cast(self, spell: str, me: Dict[str, Any]) -> bool:
        costs = {"fireball": 30, "shield": 20, "heal": 25, "teleport": 20, "summon": 50, "blink": 10}
        cd = me.get("cooldowns", {}).get(spell, 0)
        return me["mana"] >= costs.get(spell, 0) and cd == 0

    def get_dist(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
        return max(abs(p1[0] - p2[0]), abs(p1[1] - p2[1]))

    def is_near_edge(self, pos: Tuple[int, int], state: Dict[str, Any]) -> bool:
        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10
        return pos[0] <= 1 or pos[0] >= w - 2 or pos[1] <= 1 or pos[1] >= h - 2

    def manhattan_dist(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    def find_best_artifact(
        self,
        my_pos: Tuple[int, int],
        opp_pos: Tuple[int, int],
        artifacts: List[Dict[str, Any]],
        a_type: Optional[str],
    ) -> Optional[Tuple[int, int]]:
        if not artifacts:
            return None
        valid = [a for a in artifacts if a_type is None or a["type"] == a_type]
        if not valid:
            return None
        scored = []
        for a in valid:
            pos = tuple(a["position"])
            my_dist = self.get_dist(my_pos, pos)
            opp_dist = self.get_dist(opp_pos, pos)
            score = -my_dist * 2
            if my_dist < opp_dist:
                score += 10
            if opp_dist <= 1:
                score -= 20
            scored.append((score, pos))
        best = max(scored, key=lambda x: x[0])
        return best[1]

    def get_flee_move(self, my_pos: Tuple[int, int], opp_pos: Tuple[int, int], state: Dict[str, Any]) -> List[int]:
        dx = my_pos[0] - opp_pos[0]
        dy = my_pos[1] - opp_pos[1]
        move_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
        move_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10
        nx = my_pos[0] + move_x
        ny = my_pos[1] + move_y
        if 0 <= nx < w and 0 <= ny < h:
            return [move_x, move_y]
        if move_x != 0 and 0 <= my_pos[0] + move_x < w:
            return [move_x, 0]
        if move_y != 0 and 0 <= my_pos[1] + move_y < h:
            return [0, move_y]
        return [0, 0]

    def get_blink_away(self, my_pos: Tuple[int, int], opp_pos: Tuple[int, int], state: Dict[str, Any]) -> List[int]:
        dx = my_pos[0] - opp_pos[0]
        dy = my_pos[1] - opp_pos[1]
        bx = 2 if dx > 0 else (-2 if dx < 0 else 0)
        by = 2 if dy > 0 else (-2 if dy < 0 else 0)
        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10
        nx = my_pos[0] + bx
        ny = my_pos[1] + by
        if nx < 0:
            bx = -my_pos[0]
        elif nx >= w:
            bx = w - 1 - my_pos[0]
        if ny < 0:
            by = -my_pos[1]
        elif ny >= h:
            by = h - 1 - my_pos[1]
        return [bx, by]

    def get_blink_toward(self, my_pos: Tuple[int, int], target: Tuple[int, int], state: Dict[str, Any]) -> List[int]:
        dx = target[0] - my_pos[0]
        dy = target[1] - my_pos[1]
        bx = min(2, abs(dx)) * (1 if dx > 0 else -1) if dx != 0 else 0
        by = min(2, abs(dy)) * (1 if dy > 0 else -1) if dy != 0 else 0
        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10
        nx = my_pos[0] + bx
        ny = my_pos[1] + by
        if nx < 0:
            bx = -my_pos[0]
        elif nx >= w:
            bx = w - 1 - my_pos[0]
        if ny < 0:
            by = -my_pos[1]
        elif ny >= h:
            by = h - 1 - my_pos[1]
        return [bx, by]

    def get_summon_position(
        self,
        my_pos: Tuple[int, int],
        opp_pos: Tuple[int, int],
        minions: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> Optional[List[int]]:
        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10
        occupied = {tuple(my_pos), tuple(opp_pos)}
        for m in minions:
            occupied.add(tuple(m["position"]))
        dx = opp_pos[0] - my_pos[0]
        dy = opp_pos[1] - my_pos[1]
        dir_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
        dir_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
        candidates = [
            (my_pos[0] + dir_x, my_pos[1] + dir_y),
            (my_pos[0] + dir_x, my_pos[1]),
            (my_pos[0], my_pos[1] + dir_y),
            (my_pos[0] + 1, my_pos[1]),
            (my_pos[0] - 1, my_pos[1]),
            (my_pos[0], my_pos[1] + 1),
            (my_pos[0], my_pos[1] - 1),
        ]
        for cx, cy in candidates:
            if 0 <= cx < w and 0 <= cy < h and (cx, cy) not in occupied:
                return [cx, cy]
        return None

    def bfs_move(self, start: Tuple[int, int], goal: Tuple[int, int], state: Dict[str, Any]) -> List[int]:
        if start == goal:
            return [0, 0]
        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10
        obstacles = {tuple(m["position"]) for m in state.get("minions", [])}
        queue: deque[Tuple[Tuple[int, int], Optional[List[int]]]] = deque([(start, None)])
        visited = {start}
        moves = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        while queue:
            curr, first_step = queue.popleft()
            if curr == goal:
                return first_step if first_step else [0, 0]
            for dx, dy in moves:
                nx, ny = curr[0] + dx, curr[1] + dy
                next_pos = (nx, ny)
                if 0 <= nx < w and 0 <= ny < h:
                    if next_pos not in visited and (next_pos not in obstacles or next_pos == goal):
                        visited.add(next_pos)
                        next_step = [dx, dy] if first_step is None else first_step
                        queue.append((next_pos, next_step))
        dx = goal[0] - start[0]
        dy = goal[1] - start[1]
        mx = 1 if dx > 0 else (-1 if dx < 0 else 0)
        my = 1 if dy > 0 else (-1 if dy < 0 else 0)
        return [mx, my]
