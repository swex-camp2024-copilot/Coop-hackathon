from typing import List, Dict, Any, Tuple, Optional
from collections import deque

from bots.bot_interface import BotInterface


class ArchmageBot(BotInterface):
    def __init__(self) -> None:
        self.name_ = "Archmage"

    @property
    def name(self) -> str:
        return self.name_

    def decide(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Final Archmage Logic:
        1. SURVIVE: If HP < 30, Shield/Heal/Run.
        2. ATTACK: If Enemy in Range (5), Fireball.
        3. LOOT: If Low HP/Mana, go to Artifact.
        4. HUNT: Else, go to Enemy.
        """
        me = state["self"]
        opp = state["opponent"]
        my_pos = tuple(me["position"])
        opp_pos = tuple(opp["position"])

        # PRIORITY 1: SURVIVAL
        if me["hp"] < 30:
            if self.can_cast("shield", me):
                return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": {"name": "shield"}}
            if self.can_cast("heal", me):
                return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": {"name": "heal"}}
            return {"move": self.get_flee_move(my_pos, opp_pos, state), "spell": None}

        # PRIORITY 2: COMBAT
        dist = self.get_dist(my_pos, opp_pos)
        if dist <= 5 and self.can_cast("fireball", me):
            step = self.bfs_move(my_pos, opp_pos, state)
            return {"move": step, "spell": {"name": "fireball", "target": opp_pos}}

        # PRIORITY 3: RESOURCES
        target_pos: Optional[Tuple[int, int]] = None
        if me["hp"] < 80:
            target_pos = self.find_nearest(my_pos, state.get("artifacts", []), "health")
        if not target_pos and me["mana"] < 60:
            target_pos = self.find_nearest(my_pos, state.get("artifacts", []), "mana")

        # PRIORITY 4: HUNT
        if not target_pos:
            target_pos = opp_pos

        move = self.bfs_move(my_pos, target_pos, state)
        return {"move": move, "spell": None}

    # --- HELPERS ---

    def can_cast(self, spell: str, me: Dict[str, Any]) -> bool:
        costs = {"fireball": 30, "shield": 20, "heal": 25}
        cd = me.get("cooldowns", {}).get(spell, 0)
        return me["mana"] >= costs.get(spell, 0) and cd == 0

    def get_dist(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
        return max(abs(p1[0] - p2[0]), abs(p1[1] - p2[1]))

    def find_nearest(
        self,
        my_pos: Tuple[int, int],
        artifacts: List[Dict[str, Any]],
        a_type: str,
    ) -> Optional[Tuple[int, int]]:
        valid = [a for a in artifacts if a["type"] == a_type]
        if not valid:
            return None
        best = min(valid, key=lambda a: self.get_dist(my_pos, tuple(a["position"])))
        return tuple(best["position"])

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
        return [0, 0]

    def bfs_move(self, start: Tuple[int, int], goal: Tuple[int, int], state: Dict[str, Any]) -> List[int]:
        if start == goal:
            return [0, 0]

        board_size = state["board_size"]
        w = h = board_size if isinstance(board_size, int) else 10

        obstacles = {tuple(m["position"]) for m in state.get("minions", [])}

        queue: deque[Tuple[Tuple[int, int], Optional[List[int]]]] = deque([(start, None)])
        visited = {start}

        while queue:
            curr, first_step = queue.popleft()

            if curr == goal:
                return first_step if first_step else [0, 0]

            moves = [
                (0, 1),
                (0, -1),
                (1, 0),
                (-1, 0),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]

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
