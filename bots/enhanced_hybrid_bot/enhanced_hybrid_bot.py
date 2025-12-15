import random

from bots.bot_interface import BotInterface


class EnhancedBot(BotInterface):
    def __init__(self):
        self._name = "Enhanced Hybrid Bot"
        self._sprite_path = "assets/wizards/coop-rg-2-bot.png"
        self._minion_sprite_path = "assets/minions/minion-rg-2.png"
        self._first_round = True
        self._kill_mode = False  # Track if we're going for the kill

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
        opp_hp = opp_data["hp"]
        opp_mana = opp_data.get("mana", 100)

        def dist(a, b):
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))  # Chebyshev

        def manhattan_dist(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        # Calculate potential damage we can deal
        def calculate_kill_potential():
            damage = 0
            attacks = []
            
            # Melee damage (20)
            if cooldowns["melee_attack"] == 0 and manhattan_dist(self_pos, opp_pos) == 1:
                damage += 20
                attacks.append("melee")
            
            # Fireball damage (30)
            if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
                damage += 30
                attacks.append("fireball")
            
            # Can we move into melee range?
            can_move_to_melee = dist(self_pos, opp_pos) <= 2
            if cooldowns["melee_attack"] == 0 and can_move_to_melee and "melee" not in attacks:
                damage += 20  # Potential next turn
            
            return damage, attacks

        potential_damage, available_attacks = calculate_kill_potential()
        
        # Activate kill mode if we can finish opponent
        self._kill_mode = opp_hp <= potential_damage and len(available_attacks) > 0

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
        enemy_minions = enemies.copy()
        enemies.append(opp_data)

        # Count enemy threats
        my_minions = [m for m in minions if m["owner"] == self_data["name"]]
        threat_count = len(enemy_minions) + 1  # minions + opponent

        # MELEE ATTACK - KILL PRIORITY
        adjacent_enemies = [e for e in enemies if manhattan_dist(self_pos, e["position"]) == 1]
        if cooldowns["melee_attack"] == 0 and adjacent_enemies:
            for enemy in adjacent_enemies:
                # ULTRA PRIORITY for lethal blows
                if enemy == opp_data:
                    if opp_hp <= 20:
                        priority = 50  # GUARANTEED KILL on opponent
                    elif opp_hp <= 40:
                        priority = 35  # Likely kill on opponent
                    elif self._kill_mode:
                        priority = 40  # Part of kill combo
                    else:
                        priority = 25  # Regular opponent attack
                else:
                    # Minions
                    if enemy["hp"] <= 20:
                        priority = 30  # Kill minion threat
                    else:
                        priority = 18
                
                spells.append({"name": "melee_attack", "target": enemy["position"], "priority": priority})

        # FIREBALL - PRIMARY DAMAGE DEALER
        if cooldowns["fireball"] == 0 and mana >= 30 and dist(self_pos, opp_pos) <= 5:
            if opp_hp <= 30:
                priority = 48  # LETHAL SHOT
            elif opp_hp <= 50:
                priority = 38  # Heavy damage, near kill
            elif opp_hp <= 70:
                priority = 30  # Significant damage
            elif self._kill_mode:
                priority = 42  # Part of kill combo
            elif mana > 60 and hp > 50:
                priority = 26  # Aggressive with resources
            else:
                priority = 22  # Standard offense
            
            spells.append({"name": "fireball", "target": opp_pos, "priority": priority})

        # SHIELD - SURVIVAL ONLY WHEN NOT KILLING
        if cooldowns["shield"] == 0 and mana >= 20 and not self._kill_mode:
            # Check if opponent can attack us
            opp_in_fireball_range = dist(self_pos, opp_pos) <= 5
            opp_in_melee_range = manhattan_dist(self_pos, opp_pos) == 1
            
            if hp <= 40:
                priority = 32  # Critical defense
            elif hp <= 60 and (opp_in_fireball_range or opp_in_melee_range):
                priority = 28  # Defensive under threat
            elif hp <= 75:
                priority = 18
            else:
                priority = 10
            
            spells.append({"name": "shield", "priority": priority})

        # HEAL - EMERGENCY ONLY, AVOID DURING KILLS
        if cooldowns["heal"] == 0 and mana >= 25 and not self._kill_mode:
            if hp <= 25:
                priority = 45  # Emergency (but below lethal kill priority)
            elif hp <= 40:
                priority = 30
            elif hp <= 60:
                priority = 20
            elif hp <= 75:
                priority = 12
            else:
                priority = 0
            
            if priority > 0:
                spells.append({"name": "heal", "priority": priority})

        # SUMMON - TACTICAL PRESSURE
        if cooldowns["summon"] == 0 and mana >= 50 and not self._kill_mode:
            has_minion = any(m["owner"] == self_data["name"] for m in minions)
            if not has_minion:
                # Summon for number advantage and pressure
                if threat_count > len(my_minions) + 1:
                    priority = 20  # Need numbers
                elif mana > 80:
                    priority = 16  # Good mana economy
                elif hp > 70:
                    priority = 14  # Healthy, apply pressure
                else:
                    priority = 10
                
                spells.append({"name": "summon", "priority": priority})

        # TELEPORT - AGGRESSIVE POSITIONING OR ESCAPE
        if cooldowns["teleport"] == 0 and mana >= 40 and artifacts:
            if hp <= 30 and opp_hp > 50:
                # Emergency escape
                for artifact in artifacts[:2]:
                    if dist(artifact["position"], opp_pos) > dist(self_pos, opp_pos):
                        priority = 35  # Escape priority
                        spells.append({"name": "teleport", "target": artifact["position"], "priority": priority})
            elif mana <= 40 or (opp_hp <= 40 and mana < 60):
                # Need mana for the kill
                for artifact in artifacts[:2]:
                    priority = 24
                    spells.append({"name": "teleport", "target": artifact["position"], "priority": priority})
            elif dist(self_pos, opp_pos) > 7 and opp_hp < hp:
                # Aggressive reposition to close distance
                for artifact in artifacts[:1]:
                    if dist(artifact["position"], opp_pos) < dist(self_pos, opp_pos):
                        priority = 18
                        spells.append({"name": "teleport", "target": artifact["position"], "priority": priority})

        # No spell option
        spells.append({"name": None, "priority": 0})

        # KILLER EVALUATION FUNCTION
        def evaluate(move, spell_data):
            new_pos = [
                max(0, min(19, self_pos[0] + max(-1, min(1, move[0])))),
                max(0, min(19, self_pos[1] + max(-1, min(1, move[1]))))
            ]
            
            # Base score: survival + offensive capability
            score = hp * 2.0 + mana * 1.5
            
            # MASSIVE BONUS for kill spells
            if spell_data["name"]:
                priority = spell_data.get("priority", 0)
                if priority >= 45:
                    score += priority * 15  # LETHAL ATTACKS
                elif priority >= 35:
                    score += priority * 12  # High damage
                else:
                    score += priority * 7
            
            # Calculate HP advantage
            hp_advantage = hp - opp_hp
            new_dist = dist(new_pos, opp_pos)
            
            # KILL MODE: Ultra aggressive
            if self._kill_mode or opp_hp <= 50:
                # Close the distance aggressively
                score += (15 - new_dist) * 5
                
                # Bonus for getting into optimal attack range
                if new_dist <= 5 and mana >= 30:  # Fireball range
                    score += 30
                if manhattan_dist(new_pos, opp_pos) <= 1:  # Melee range
                    score += 25
                
                # Penalty for moving away
                if new_dist > dist(self_pos, opp_pos):
                    score -= 20
            
            # DOMINANT: Press advantage hard
            elif hp > 70 and hp_advantage > 15:
                score += (12 - new_dist) * 3.5
                
                # Sweet spot at fireball range
                if new_dist >= 3 and new_dist <= 5:
                    score += 25
            
            # DEFENSIVE: Survive and regroup
            elif hp <= 40 or hp_advantage < -15:
                score += new_dist * 4  # Maximize distance
                
                # Move toward artifacts
                if artifacts:
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (12 - dist(new_pos, nearest_artifact["position"])) * 6
                
                # Avoid corners when retreating
                if new_pos[0] <= 2 or new_pos[0] >= 17 or new_pos[1] <= 2 or new_pos[1] >= 17:
                    score -= 15
            
            # BALANCED: Maintain optimal range
            else:
                optimal_range = 4  # Fireball sweet spot
                range_diff = abs(new_dist - optimal_range)
                score += (8 - range_diff) * 2
                
                # Artifact awareness for sustainability
                if artifacts and (mana < 60 or hp < 70):
                    nearest_artifact = min(artifacts, key=lambda a: dist(new_pos, a["position"]))
                    score += (10 - dist(new_pos, nearest_artifact["position"])) * 3
            
            # PENALTIES
            # Don't get into melee when low HP unless it's a kill
            if hp <= 50 and manhattan_dist(new_pos, opp_pos) == 1 and not self._kill_mode:
                score -= 30
            
            # Avoid edges (limited mobility)
            if new_pos[0] == 0 or new_pos[0] == 19 or new_pos[1] == 0 or new_pos[1] == 19:
                score -= 12
            
            # BONUSES
            # Central positioning (better options)
            center = [9, 9]
            score += (15 - dist(new_pos, center)) * 0.5
            
            # Bonus for positioning between opponent and their artifacts
            if artifacts:
                for artifact in artifacts[:2]:
                    if dist(new_pos, artifact["position"]) < dist(opp_pos, artifact["position"]):
                        if dist(new_pos, opp_pos) <= 6:
                            score += 8  # Cut off their resources
            
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