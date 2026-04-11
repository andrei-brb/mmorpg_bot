"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              cogs/combat/combat_cog.py — /fight /rest commands             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import CLASSES, ENEMIES, ZONES, RARITIES, Settings, ABILITY_UNLOCK_LEVELS
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.lore.lore_gate_service import LoreGateService
from services.combat.combat_engine import (
    ABILITIES, CombatEngine, CombatResult, CombatSession, Combatant
)

log = logging.getLogger("cog.combat")


# Imported from config.settings to keep the function testable without discord
from config.settings import _boss_hp_scale_for_zone

# Channel-level lock: channel_id -> CombatSession
ACTIVE: Dict[int, CombatSession] = {}


async def _safe_edit(msg, embed, view=None, max_retries=3):
    """Edit message with retry on Discord 429 rate limit."""
    for attempt in range(max_retries):
        try:
            await msg.edit(embed=embed, view=view)
            return
        except discord.errors.HTTPException as e:
            if e.status == 429 and attempt < max_retries - 1:
                wait = (attempt + 1) * 2.0  # 2s, 4s, 6s
                log.warning(f"Discord rate limit (429), waiting {wait}s before retry")
                await asyncio.sleep(wait)
            else:
                raise


def _make_enemy(key: str, char_level: int, zone=None) -> Combatant:
    tmpl = ENEMIES.get(key, ENEMIES["kobold"])
    scale = 1 + char_level * 0.06
    hp = int(tmpl.hp_base * scale)
    if tmpl.is_boss:
        boss_scale = _boss_hp_scale_for_zone(zone) if zone is not None else Settings.BOSS_HP_SCALE
        hp = int(hp * boss_scale)
    return Combatant(
        id=str(uuid4()), name=f"{tmpl.emoji} {tmpl.name}",
        is_player=False, char_id=None,
        current_hp=hp, max_hp=hp, current_res=0, max_res=0,
        res_type="none",
        attack_power=int(tmpl.attack_power * scale),
        dmg_min=int(tmpl.damage_min * scale),
        dmg_max=int(tmpl.damage_max * scale),
        armor=int(tmpl.armor * scale),
        crit_chance=tmpl.crit_chance,
    )


def _make_player(char, stats) -> Combatant:
    from services.character.character_service import CharacterService

    char = CharacterService.normalize_resources(dict(char))
    cls = CLASSES[char["class"]]
    return Combatant(
        id=str(char["id"]), name=char["name"],
        is_player=True, char_id=char["id"],
        current_hp=char["current_hp"], max_hp=char["max_hp"],
        current_res=char["current_res"], max_res=char["max_res"],
        specialization=char.get("specialization"),
        res_type=cls.resource,
        attack_power=stats["attack_power"],
        spell_power=stats["spell_power"],
        dmg_min=stats.get("dmg_min", 8) or 8,
        dmg_max=stats.get("dmg_max", 16) or 16,
        armor=stats["armor"],
        crit_chance=stats["crit_chance"],
        dodge_chance=stats["dodge_chance"],
        haste=stats.get("haste", 0.0),
        lifesteal=stats.get("lifesteal", 0.0),
        resistance=stats.get("resistance", 0),
        hit_rating=stats.get("hit_rating", 0.0),
        class_key=char.get("class"),
    )


def _hp_bar(cur, mx, length=10):
    filled = int((cur / mx) * length) if mx else 0
    return "█" * filled + "░" * (length - filled)

def _res_bar(cur, mx, length=10):
    filled = int((cur / mx) * length) if mx else 0
    return "█" * filled + "░" * (length - filled)

def _res_label(res_type: str) -> str:
    return {"mana": "💙 Mana", "energy": "⚡ Energy", "rage": "🔴 Rage"}.get(res_type, "🔋 Resource")


def _build_embed(session: CombatSession, log_lines: list[str]) -> discord.Embed:
    alive_players = session.alive_players if session.alive_players else session.players
    e = session.alive_enemies[0]  if session.alive_enemies  else session.enemies[0]

    e_eff = " ".join(f"*{s.effect.value}*" for s in e.status_effects)

    embed = discord.Embed(title=f"⚔️ Combat — Turn {session.turn}", color=0xCC2222)
    
    # Show all party members
    if len(alive_players) > 1:
        embed.add_field(
            name="👥 Party",
            value="\n".join([
                f"**{p.name}** `{_hp_bar(p.current_hp, p.max_hp)}` {p.current_hp}/{p.max_hp} HP"
                + (f" | `{_res_bar(p.current_res, p.max_res)}` {p.current_res}/{p.max_res} {_res_label(p.res_type)}" if p.max_res > 0 else "")
                + (" 💀" if p.is_dead else "")
                for p in alive_players
            ]),
            inline=False,
        )
    else:
        # Single player (backwards compatible)
        p = alive_players[0]
        p_eff = " ".join(f"*{s.effect.value}*" for s in p.status_effects)
        player_value = f"`{_hp_bar(p.current_hp, p.max_hp)}` **{p.current_hp}/{p.max_hp}** ❤️ HP"
        if p.max_res > 0:
            player_value += f"\n`{_res_bar(p.current_res, p.max_res)}` **{p.current_res}/{p.max_res}** {_res_label(p.res_type)}"
        if p_eff:
            player_value += f"\n{p_eff}"
        embed.add_field(
            name=f"🧙 {p.name}",
            value=player_value,
            inline=False,
        )
    
    embed.add_field(
        name=f"{e.name}",
        value=(
            f"`{_hp_bar(e.current_hp, e.max_hp)}` {e.current_hp}/{e.max_hp} HP"
            + (f"\n`{_res_bar(e.current_res, e.max_res)}` {e.current_res}/{e.max_res} {_res_label(e.res_type)}" if e.max_res > 0 else "")
            + (f"\n{e_eff}" if e_eff else "")
        ),
        inline=False,
    )
    if log_lines:
        embed.add_field(name="📜 Battle Log", value="\n".join(log_lines[-5:]), inline=False)
    return embed


class AbilityView(discord.ui.View):
    def __init__(self, char, combatant: Combatant, owner_id: int = None, can_use_potion: bool = False):
        super().__init__(timeout=Settings.COMBAT_TIMEOUT_SECONDS)
        self.chosen         = None
        self.fled           = False
        self.owner_id       = owner_id
        self.can_use_potion = can_use_potion

        cls = CLASSES[char["class"]]
        keys = ["auto_attack"] + list(cls.starter_abilities)
        if char.get("specialization"):
            from config.settings import SPECIALIZATIONS
            spec = SPECIALIZATIONS.get(char["specialization"])
            if spec:
                keys.extend(spec.bonus_abilities)

        options = []
        cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
        char_level = char.get("level", 1)
        for key in dict.fromkeys(keys):  # deduplicate, preserve order
            ab = ABILITIES.get(key)
            if not ab: continue
            
            # Check if ability is unlocked
            unlock_level = ABILITY_UNLOCK_LEVELS.get(key, 1)  # Default to level 1 if not specified
            if char_level < unlock_level:
                continue  # Skip abilities that aren't unlocked yet
            cd = combatant.ability_cooldowns.get(key, 0)
            eff_cost = int(ab.cost * cost_mult) if ab.cost else 0
            cost = f"({eff_cost} {ab.cost_type})" if eff_cost else ""
            cd_str = f" [CD:{cd}]" if cd else ""
            # Only use emoji if it's a single character/emoji (Discord rejects multi-emoji)
            emoji = ab.emoji if len(ab.emoji) <= 2 else None
            options.append(discord.SelectOption(
                label=f"{ab.name} {cost}{cd_str}",
                value=key,
                description=ab.description[:80],
                emoji=emoji,
            ))

        sel = discord.ui.Select(placeholder="Choose your ability…", options=options[:25])
        sel.callback = self._pick
        self.add_item(sel)

        # Disable potion button if player can't use one this turn
        if not self.can_use_potion:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and getattr(item, "label", "") == "🧪 Potion":
                    item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        log.debug(f"[COMBAT LOCK] owner_id={self.owner_id}, clicker={interaction.user.id} ({interaction.user.display_name})")
        if self.owner_id and interaction.user.id != self.owner_id:
            log.debug(f"[COMBAT LOCK] BLOCKED {interaction.user.display_name} from using combat")
            await interaction.response.send_message(
                "❌ **This isn't your fight!** Only the player in combat can use these buttons.", ephemeral=True
            )
            return False
        return True

    async def _pick(self, interaction: discord.Interaction):
        try:
            self.chosen = interaction.data["values"][0]
            self.stop()  # Stop FIRST
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception as e:
                log.warning(f"Error deferring ability selection: {e}")
        except Exception as e:
            log.error(f"Error in ability selection: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred selecting ability.", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.grey, row=1)
    async def flee(self, interaction: discord.Interaction, _):
        try:
            self.fled = True
            self.stop()
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception as e:
                log.warning(f"Error deferring flee: {e}")
        except Exception as e:
            log.error(f"Error in flee: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while fleeing.", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="🧪 Potion", style=discord.ButtonStyle.green, row=1)
    async def use_potion(self, interaction: discord.Interaction, _):
        """Signal that the player wants to use a healing potion this turn."""
        try:
            if not self.can_use_potion:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ You can't use a potion right now.", ephemeral=True
                    )
                return
            self.chosen = "__potion__"
            self.stop()
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception as e:
                log.warning(f"Error deferring potion use: {e}")
        except Exception as e:
            log.error(f"Error in potion button: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An error occurred while using a potion.", ephemeral=True
                    )
            except Exception:
                pass
    async def on_timeout(self):
        self.chosen = "auto_attack"
        self.stop()


class EnemySelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, zone, char_level: int):
        super().__init__(timeout=30)  # 30 seconds to select enemy
        self.owner_id = owner_id
        self.chosen = None
        self.add_item(_EnemySelect(zone, char_level))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # Timeout handled in fight() method
        self.chosen = None
        self.stop()

class _EnemySelect(discord.ui.Select):
    def __init__(self, zone, char_level: int):
        options: List[discord.SelectOption] = []
        
        # Add regular enemies first
        for enemy_key in zone.enemies:
            enemy = ENEMIES.get(enemy_key)
            if not enemy:
                continue
            scale = 1 + char_level * 0.06
            hp = int(enemy.hp_base * scale)
            options.append(discord.SelectOption(
                label=enemy.name,
                description=f"Regular enemy • ~{hp} HP",
                value=enemy_key,
                emoji=enemy.emoji,
            ))
        
        # Add bosses (marked with ⭐)
        for boss_key in zone.bosses:
            boss = ENEMIES.get(boss_key)
            if not boss:
                continue
            scale = 1 + char_level * 0.06
            hp = int(boss.hp_base * scale * _boss_hp_scale_for_zone(zone))
            options.append(discord.SelectOption(
                label=f"⭐ {boss.name}",
                description=f"BOSS • ~{hp} HP • Better rewards!",
                value=boss_key,
                emoji=boss.emoji,
            ))
        
        super().__init__(
            placeholder="Choose an enemy to fight…",
            min_values=1,
            max_values=1,
            options=options[:25],  # Discord limit
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view
            if not isinstance(view, EnemySelectView):
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Internal error.", ephemeral=True)
                return
            if interaction.user.id != view.owner_id:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
                return
            
            view.chosen = self.values[0]
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception as e:
                log.warning(f"Error deferring enemy selection: {e}")
            view.stop()  # Stop the VIEW (not the Select)
        except Exception as e:
            log.error(f"Error in enemy selection: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred selecting enemy.", ephemeral=True)
            except Exception:
                pass


class CombatCog(commands.Cog, name="Combat"):
    def __init__(self, bot):
        self.bot = bot
        self.engine = CombatEngine()
        self.char_svc: CharacterService = None
        self.inv_svc:  InventoryService = None
        self.lore_gate: LoreGateService = None

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc  = InventoryService(self.bot.db)
        self.lore_gate = LoreGateService(self.bot.db)

    # ── /fight ────────────────────────────────────────────────────────────────

    @app_commands.command(name="fight", description="Engage an enemy in your current zone")
    @app_commands.describe(target="Specific enemy to fight (optional)")
    async def fight(self, interaction: discord.Interaction, target: Optional[str] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "fight"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character. Use `/character create`.")

        from services.combat.activity_combat import ACTIVE_ACTIVITY

        if interaction.user.id in ACTIVE_ACTIVITY:
            return await interaction.followup.send(
                "⚔️ You're already fighting in the **Activity** (Embedded App). Finish or flee there first."
            )

        # Check if stuck in combat (status says in_combat but no active session)
        if char["combat_status"] == "in_combat":
            channel_has_combat = interaction.channel_id in ACTIVE
            activity_has_combat = interaction.user.id in ACTIVE_ACTIVITY
            if not channel_has_combat and not activity_has_combat:
                # Stuck in combat - clear it automatically
                await self.bot.db.execute(
                    "UPDATE characters SET combat_status='idle' WHERE id=$1",
                    char["id"],
                )
                # Refresh char data
                char = await self.char_svc.get_character(interaction.user.id)
            else:
                return await interaction.followup.send("⚔️ You're already in combat!")

        if interaction.channel_id in ACTIVE:
            return await interaction.followup.send("⚔️ Another combat is active in this channel.")

        zone = ZONES.get(char["current_zone"])
        if not zone:
            return await interaction.followup.send("❌ Unknown zone.")
        if char["level"] < zone.level_range[0]:
            return await interaction.followup.send(
                f"❌ This zone requires level **{zone.level_range[0]}**. Use `/travel` to find a safer area."
            )

        # If no target provided, check for pending encounter (boss from explore)
        if not target:
            pending = char.get("pending_encounter")
            if pending and pending in zone.bosses:
                # Auto-start with the specific boss found during explore
                target = pending
                # Clear pending encounter
                await self.bot.db.execute(
                    "UPDATE characters SET pending_encounter=NULL WHERE id=$1",
                    char["id"],
                )
            else:
                # Show selection menu for normal enemies or manual boss selection
                view = EnemySelectView(owner_id=interaction.user.id, zone=zone, char_level=char["level"])
                msg = await interaction.followup.send(
                    f"**Select an enemy to fight in {zone.emoji} {zone.name}:**\n"
                    f"⭐ = Boss (better rewards, harder fight)\n"
                    f"⏰ You have 30 seconds to select, or you'll automatically flee.",
                    view=view,
                    ephemeral=True,
                )
                await view.wait()
                if not view.chosen:
                    # Auto-flee after timeout
                    await self.bot.db.execute(
                        "UPDATE characters SET combat_status='idle', pending_encounter=NULL WHERE id=$1",
                        char["id"],
                    )
                    return await msg.edit(content="⏰ **Time's up!** You didn't select an enemy in time. Combat cancelled.", view=None)
                target = view.chosen
                # Clear pending encounter if it was set
                if pending:
                    await self.bot.db.execute(
                        "UPDATE characters SET pending_encounter=NULL WHERE id=$1",
                        char["id"],
                    )
                # Edit the message to show selection
                await msg.edit(content=f"⚔️ Starting fight with **{ENEMIES.get(target, ENEMIES['kobold']).name}**...", view=None)

        enemy_key = target
        await self._start_combat(interaction, char, enemy_key)

    async def _start_combat(self, interaction, char: dict, enemy_key: str):
        """Helper method to start combat - can be called from fight command or explore."""
        zone = ZONES.get(char["current_zone"])
        if not zone:
            return await interaction.followup.send("❌ Unknown zone.")
        
        is_boss   = enemy_key in zone.bosses
        stats     = await self.char_svc.total_stats(char["id"])

        player_c  = _make_player(dict(char), stats)
        enemy_c   = _make_enemy(enemy_key, char["level"], zone)

        session = CombatSession(
            session_id=uuid4(),
            players=[player_c],
            enemies=[enemy_c],
            is_boss=is_boss,
            enemy_key=enemy_key,
            zone_key=char["current_zone"],
            apply_lore_gates=True,
        )
        from services.lore.lore_gate_service import LoreGateService

        lg = LoreGateService(self.bot.db)
        session.lore_gate_by_char, session.lore_gate_hint = await lg.evaluate_characters(
            [char["id"]], enemy_key, apply_lore_gates=True
        )
        ACTIVE[interaction.channel_id] = session

        # Clear pending_encounter and set combat status
        await self.bot.db.execute(
            "UPDATE characters SET combat_status='in_combat', last_combat=NOW(), pending_encounter=NULL WHERE id=$1",
            char["id"],
        )

        await self._run(interaction, session, dict(char))

    @fight.autocomplete("target")
    async def fight_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for enemy/boss names in /fight."""
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return []
        zone = ZONES.get(char["current_zone"])
        if not zone:
            return []

        current_l = (current or "").lower()
        choices = []

        # Regular enemies
        for key in zone.enemies:
            enemy = ENEMIES.get(key)
            if not enemy:
                continue
            if current_l in key.lower() or current_l in enemy.name.lower():
                choices.append(app_commands.Choice(
                    name=f"{enemy.emoji} {enemy.name}",
                    value=key,
                ))

        # Bosses (marked with ⭐)
        for key in zone.bosses:
            boss = ENEMIES.get(key)
            if not boss:
                continue
            if current_l in key.lower() or current_l in boss.name.lower():
                choices.append(app_commands.Choice(
                    name=f"⭐ {boss.emoji} {boss.name} (BOSS)",
                    value=key,
                ))

        return choices[:25]

    async def _run(self, interaction, session: CombatSession, char: dict):
        char_id  = char["id"]
        log_lines: list[str] = []
        msg = None
        potion_used = False  # Limit to one potion per fight for now
        fled_successfully = False
        
        # Ensure combat status is cleared even if combat crashes
        try:
            while not session.over:
                session.turn += 1
                player = session.alive_players[0]
                enemy  = session.alive_enemies[0]

                # ── Player start-of-turn ──────────────────────────────────────────
                ticks = self.engine.tick_turn(player)
                if ticks: log_lines.extend(ticks)
                if player.is_dead: break

                # ── Show UI ───────────────────────────────────────────────────────
                try:
                    fresh = await self.char_svc.get_character(interaction.user.id)
                    # Check if player has at least one healing potion available
                    has_potion_row = await self.bot.db.fetchrow(
                        """
                        SELECT i.id, t.name, t.effect_value
                        FROM inventory i
                        JOIN item_templates t ON i.template_id = t.id
                        WHERE i.character_id = $1
                          AND i.quantity > 0
                          AND t.item_type = 'consumable'
                          AND t.effect_type = 'heal_hp'
                        ORDER BY t.effect_value DESC
                        LIMIT 1
                        """,
                        char_id,
                    )
                    can_use_potion = bool(has_potion_row) and not potion_used

                    view  = AbilityView(dict(fresh), player, owner_id=interaction.user.id, can_use_potion=can_use_potion)
                    embed = _build_embed(session, log_lines)

                    if msg:
                        await _safe_edit(msg, embed, view=view)
                    else:
                        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

                    await view.wait()
                except Exception as e:
                    log.error(f"Error in combat UI: {e}", exc_info=True)
                    # If UI fails, default to auto attack and continue
                    view = type('View', (), {'chosen': 'auto_attack', 'fled': False})()
                    log_lines.append("⚠️ UI error - using auto attack")

                # ── Flee ──────────────────────────────────────────────────────────
                if view.fled:
                    flee_roll = Settings.FLEE_BASE_CHANCE + player.dodge_chance * 0.01
                    if random.random() < flee_roll:
                        log_lines.append("🏃 You escaped!")
                        fled_successfully = True
                        await self.bot.db.execute(
                            "UPDATE characters SET combat_status='idle' WHERE id=$1",
                            char_id,
                        )
                        break
                    else:
                        log_lines.append("🚫 You couldn't flee!")
                        # Don't give enemy a free hit — flee attempt replaces your turn
                        try:
                            if msg:
                                await _safe_edit(msg, _build_embed(session, log_lines), view=None)
                        except Exception:
                            pass
                        continue

                else:
                    # ── Player action ─────────────────────────────────────────────
                    try:
                        # Potion use has priority over abilities
                        if view.chosen == "__potion__":
                            if not has_potion_row:
                                log_lines.append("❌ You don't have any healing potions!")
                            elif player.current_hp >= player.max_hp:
                                log_lines.append("❌ You are already at full health.")
                            else:
                                potion_id = has_potion_row["id"]
                                ok, msg_text, effect = await self.inv_svc.use_consumable(char_id, potion_id)
                                healed = 0
                                if ok and effect and effect.get("type") == "heal_hp":
                                    base_val = int(effect.get("value") or 80)
                                    heal_val = max(base_val, player.max_hp // 4)  # 25% of max, min 80
                                    room = max(0, player.max_hp - player.current_hp)
                                    healed = min(heal_val, room)
                                    player.current_hp += healed
                                    if healed > 0:
                                        await self.char_svc.set_current_hp_res(
                                            char_id, player.current_hp, player.current_res
                                        )
                                    log_lines.append(f"🧪 {msg_text} Restored **{healed}** HP.")
                                else:
                                    log_lines.append(f"🧪 {msg_text}")
                                potion_used = ok or potion_used
                            # Skip ability casting this turn
                            continue

                        ab_key = view.chosen or "auto_attack"
                        if not ab_key:
                            ab_key = "auto_attack"
                            log.warning(f"No ability chosen, defaulting to auto_attack")
                        
                        ab = ABILITIES.get(ab_key)
                        if not ab:
                            log.error(f"Ability '{ab_key}' not found, using auto_attack")
                            ab = ABILITIES.get("auto_attack", ABILITIES["auto_attack"])
                        
                        cls = CLASSES[char["class"]]
                        cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
                        eff_cost = int(ab.cost * cost_mult) if ab.cost else 0

                        # Resource check
                        if ab.cost_type in ("mana", "energy", "rage") and player.current_res < eff_cost:
                            # Don't let a failed selection "skip" the player's turn (feels like the enemy hit instead).
                            # Fall back to auto attack so the player still acts this turn.
                            log_lines.append(f"❌ Not enough {ab.cost_type} for **{ab.name}** — using **Auto Attack** instead.")
                            results = self.engine.use_ability("auto_attack", player, [enemy], session=session)
                            for r in results:
                                log_lines.append(r.narrative)
                            session.log.extend(results)
                        elif ab_key in player.ability_cooldowns:
                            log_lines.append(f"⏳ **{ab.name}** is on cooldown — using **Auto Attack** instead.")
                            results = self.engine.use_ability("auto_attack", player, [enemy], session=session)
                            for r in results:
                                log_lines.append(r.narrative)
                            session.log.extend(results)
                        else:
                            if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
                                player.current_res = max(0, player.current_res - eff_cost)
                            results = self.engine.use_ability(ab_key, player, [enemy], session=session)
                            for r in results:
                                log_lines.append(r.narrative)
                            session.log.extend(results)
                            # Ability mastery progression (lightweight).
                            try:
                                await self.char_svc.award_ability_mastery_xp(char_id, ab_key, 1)
                            except Exception:
                                pass
                    except Exception as e:
                        log.error(f"Error executing ability '{ab_key}': {e}", exc_info=True)
                        error_msg = str(e)[:100]  # Truncate long errors
                        log_lines.append(f"⚠️ Error using **{ab.name}**: {error_msg}")
                        # Fallback to auto attack
                        try:
                            results = self.engine.use_ability("auto_attack", player, [enemy], session=session)
                            for r in results:
                                log_lines.append(r.narrative)
                            session.log.extend(results)
                        except Exception as e2:
                            log.error(f"Error with auto attack fallback: {e2}", exc_info=True)
                            log_lines.append(f"💥 Critical: Auto attack also failed!")

                if session.over: break

                # ── Enemy start-of-turn ───────────────────────────────────────────
                e_ticks = self.engine.tick_turn(enemy)
                if e_ticks: log_lines.extend(e_ticks)

                if not enemy.is_dead:
                    if session.is_boss:
                        session.boss_phase = self.engine.boss_phase(enemy)
                    e_ab, e_targets = self.engine.enemy_turn(
                        enemy, session.alive_players, session.is_boss, session.boss_phase, enemy_key=session.enemy_key
                    )
                    if e_targets:
                        e_results = self.engine.use_ability(e_ab, enemy, e_targets, session=session)
                        for r in e_results:
                            log_lines.append(r.narrative)
                        session.log.extend(e_results)

                # Update the embed with new log
                try:
                    if msg:
                        await _safe_edit(msg, _build_embed(session, log_lines), view=None)
                except Exception as e:
                    log.error(f"Error updating combat embed: {e}", exc_info=True)
                    # Try to send a new message if edit fails
                    try:
                        if interaction.followup:
                            await interaction.followup.send(
                                embed=_build_embed(session, log_lines),
                                ephemeral=True
                            )
                    except Exception:
                        pass

        # ── Combat ended ──────────────────────────────────────────────────────
        finally:
            # Always clear active combat and combat status, even if there was an error
            ACTIVE.pop(interaction.channel_id, None)
            try:
                # Double-check combat status is cleared
                await self.bot.db.execute(
                    "UPDATE characters SET combat_status='idle' WHERE id=$1",
                    char_id,
                )
            except Exception as e:
                log.error(f"Error clearing combat status: {e}", exc_info=True)
        
        player = session.players[0]

        if fled_successfully:
            await self._fled(interaction, char, player, msg)
        elif session.players_won:
            await self._victory(interaction, session, char, player, msg)
        else:
            await self._defeat(interaction, char, player, msg)

    async def _victory(self, interaction, session, char, player: Combatant, msg=None):
        from services.reward_multipliers import get_combined_reward_multipliers

        xp_mult, gold_mult, _boss_add = await get_combined_reward_multipliers(
            self.bot.db, interaction.guild_id
        )

        rewards = self.engine.calculate_rewards(session)

        if getattr(Settings, "COMBAT_AWARD_XP_ON_VICTORY", True):
            xp_result = await self.char_svc.award_xp(char["id"], rewards["xp"], xp_mult)
        else:
            xp_result = {
                "leveled_up": False,
                "old_level": char.get("level", 1),
                "new_level": char.get("level", 1),
                "levels_gained": 0,
                "xp_gained": 0,
            }
        gold_earned = int(rewards["gold"] * gold_mult)
        await self.char_svc.add_gold(char["id"], gold_earned, "combat drop")
        await self.char_svc.sync_combat_hp(char["id"], player.current_hp, player.current_res)
        # Class mastery progression (victory-based; boss fights grant more).
        try:
            base_gain = 8 + (6 if session.is_boss else 0)
            await self.char_svc.award_class_mastery_xp(char["id"], char.get("class") or "", base_gain)
        except Exception:
            pass

        # Loot rolls
        loot_lines = []
        for _ in range(rewards["loot_rolls"]):
            loot = await self.inv_svc.generate_loot(char["current_zone"], char["level"], session.is_boss)
            if loot:
                ok, _ = await self.inv_svc.add_item(
                    char["id"], loot["template"]["id"], loot["rarity"], bonus=loot["bonus"]
                )
                if ok:
                    rc = RARITIES[loot["rarity"]]
                    loot_lines.append(f"{rc.emoji} **{loot['template']['name']}** [{loot['rarity'].title()}]")

        # Chance to refill health potion after fight (25% base, 35% on boss)
        potion_chance = 0.35 if session.is_boss else 0.25
        if random.random() < potion_chance:
            ok, _ = await self.inv_svc.add_item(char["id"], "health_potion", "common", from_="combat_drop")
            if ok:
                loot_lines.append("🧪 **Health Potion** (refill)")

        # Check achievements (non-blocking)
        try:
            from services.achievement.achievement_service import AchievementService
            ach_svc = AchievementService(self.bot.db)
            newly_earned = await ach_svc.check_and_award(
                char["id"], "kill", {"is_boss": session.is_boss}
            )
            for ach_id in (newly_earned or []):
                ach = await ach_svc.get_achievement(ach_id)
                if ach:
                    loot_lines.append(f"🏆 **Achievement Unlocked:** {ach.get('icon', '🏆')} {ach['name']}!")
        except Exception:
            pass

        # ── Quest progress check (non-blocking) ──────────────────────────
        quest_lines = []
        quest_step_updates = []
        quest_completions = []
        try:
            from services.quest.npc_quest_service import NPCQuestService
            quest_svc = NPCQuestService(self.bot.db)
            events = await quest_svc.check_kill_progress_events(
                char["id"], session.enemy_key, session.zone_key, session.is_boss
            )
            quest_lines.extend(events.get("notifications") or [])
            quest_step_updates.extend(events.get("step_updates") or [])
            quest_completions.extend(events.get("completed") or [])
        except Exception as e:
            log.error(f"Quest progress check failed: {e}", exc_info=True)  # FIX: Use error level and include traceback

        # ── Quest step update / completion DMs (best-effort) ─────────────
        if quest_step_updates or quest_completions:
            try:
                from services.quest.npc_quest_service import NPC_TEMPLATES, FACTIONS, is_main_story_quest
                dm = await interaction.user.create_dm()

                # Step updates: only DM when the objective changes (rare, not per-kill spam).
                for upd in quest_step_updates[:3]:
                    qd = upd.get("quest_data") or {}
                    ns = upd.get("next_step") or {}
                    embed = discord.Embed(
                        title=f"📜 {qd.get('name', upd.get('quest_id', 'Quest'))} — Step Updated!",
                        description=qd.get("dialogue", {}).get(
                            f"progress_{int(ns.get('step', 1)) - 2}",
                            "\"Good progress! Keep going.\"",
                        ),
                        color=0xF39C12,
                    )
                    embed.add_field(
                        name="📍 Next Objective",
                        value=f"{ns.get('objective','')}\n*{ns.get('hint','')}*",
                        inline=False,
                    )
                    embed.set_footer(text="Tip: Check the Activity → Quests tab for a live quest log.")
                    await dm.send(embed=embed)

                # Completions: auto-grant rewards and DM the reward summary.
                for comp in quest_completions[:3]:
                    qid = comp.get("quest_id")
                    qd = comp.get("quest_data") or {}
                    rewards = comp.get("rewards") or {}
                    npc_id = comp.get("npc_id")
                    npc_data = NPC_TEMPLATES.get(npc_id, {}) if npc_id else {}

                    # Grant rewards (XP, gold, items) + reputation.
                    q_xp_result: dict = {}
                    if rewards.get("xp"):
                        q_xp_result = await self.char_svc.award_xp(char["id"], int(rewards["xp"]))
                    if rewards.get("gold"):
                        await self.char_svc.add_gold(char["id"], int(rewards["gold"]), "quest_reward", "quest_reward")
                    if rewards.get("items"):
                        for template_id in rewards["items"]:
                            tmpl = await self.bot.db.fetchrow(
                                "SELECT rarity FROM item_templates WHERE id = $1", template_id
                            )
                            rarity = tmpl["rarity"] if tmpl else "common"
                            await self.inv_svc.add_item(char["id"], template_id, rarity=rarity)

                    q_lvl = int(
                        (q_xp_result or {}).get("new_level")
                        or xp_result.get("new_level")
                        or char.get("level")
                        or 1
                    )
                    q_zone = str(char.get("current_zone") or "elwynn_forest")
                    bonus_g, bonus_f = await self.inv_svc.grant_main_story_quest_gear_bonus_if_needed(
                        char["id"],
                        is_main_story=is_main_story_quest(str(qid or "")),
                        template_item_reward_ids=list(rewards.get("items") or []),
                        zone_key=q_zone,
                        char_level=q_lvl,
                    )

                    rep_lines = []
                    if rewards.get("reputation"):
                        for faction_id, amount in rewards["reputation"].items():
                            rep_info = await quest_svc.add_reputation(char["id"], faction_id, int(amount))
                            faction = FACTIONS.get(faction_id, {})
                            rep_text = f"{faction.get('emoji', '⭐')} **+{int(amount)}** {faction.get('name', faction_id)}"
                            if rep_info.get("leveled_up"):
                                rep_text += f" — 🎊 **{rep_info['level']['name']}** reached!"
                            rep_lines.append(rep_text)

                    if rewards.get("deed_flags") and self.lore_gate:
                        await self.lore_gate.grant_deed_flags_from_rewards(char["id"], rewards)

                    embed = discord.Embed(
                        title=f"🎉 Quest Complete: {qd.get('name', qid or 'Quest')}",
                        description=qd.get("dialogue", {}).get("completion", "Quest complete!"),
                        color=0x2ECC71,
                    )

                    reward_text = []
                    if rewards.get("xp"):
                        reward_text.append(f"⭐ **{int(rewards['xp']):,}** XP")
                    if rewards.get("gold"):
                        reward_text.append(f"🪙 **{int(rewards['gold']):,}** Gold")
                    item_ids_for_display = list(rewards.get("items") or []) + bonus_g
                    if item_ids_for_display:
                        item_names = [str(i).replace("_", " ").title() for i in item_ids_for_display]
                        reward_text.append(f"🎁 {', '.join(item_names)}")
                    if bonus_f:
                        bf0 = bonus_f[0]
                        reward_text.append(
                            "⚠ Story gear bonus could not be delivered: "
                            + str(bf0.get("template_id", "item")).replace("_", " ").title()
                            + f" ({bf0.get('reason', 'inventory full')})"
                        )
                    reward_text.extend(rep_lines)
                    if reward_text:
                        embed.add_field(name="🏆 Rewards", value="\n".join(reward_text), inline=False)

                    # Next quest prompt (if this NPC has more).
                    if npc_id:
                        completed_quest_ids = [q["quest_id"] for q in await quest_svc.get_completed_quests(char["id"])]
                        deed_set = set(await self.lore_gate.get_flags(char["id"]))
                        next_quest = quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids, deed_set)
                        if next_quest:
                            npc_short = (npc_data.get("name") or npc_id).split(" ")[0].lower()
                            embed.add_field(
                                name="💬 More Work Available",
                                value=f"*{npc_data.get('name', npc_id)} has another task for you.\nUse `/interact {npc_short}` to hear them out.*",
                                inline=False,
                            )

                    embed.set_footer(text="Tip: The Activity → Quests tab also updates automatically.")
                    await dm.send(embed=embed)

            except discord.Forbidden:
                # Can't DM user (privacy settings). We already show quest_lines in the victory embed.
                pass
            except Exception:
                pass

        embed = discord.Embed(
            title="🏆 Victory!",
            description=f"You defeated **{session.enemies[0].name}**!",
            color=0x00FF7F,
        )
        xp_show = int(xp_result.get("xp_gained", rewards["xp"]))
        embed.add_field(
            name="⚡ Rewards",
            value=f"+**{xp_show:,}** XP  |  +**{gold_earned:,}**🪙",
            inline=False,
        )

        if xp_result["leveled_up"]:
            embed.add_field(
                name="🎉 LEVEL UP!",
                value=f"**{xp_result['old_level']} → {xp_result['new_level']}**",
                inline=False,
            )
            # Check level-up achievements
            try:
                newly_earned = await ach_svc.check_and_award(
                    char["id"], "level_up", {"level": xp_result["new_level"]}
                )
                for ach_id in (newly_earned or []):
                    ach = await ach_svc.get_achievement(ach_id)
                    if ach:
                        loot_lines.append(f"🏆 **Achievement:** {ach.get('icon', '🏆')} {ach['name']}!")
            except Exception:
                pass
            
            if xp_result["new_level"] == Settings.SPEC_UNLOCK_LEVEL and not char.get("specialization"):
                embed.add_field(
                    name="⚡ Specialization Unlocked!",
                    value="Use `/character specialize` to choose your path!",
                    inline=False,
                )

        if loot_lines:
            embed.add_field(name="📦 Loot", value="\n".join(loot_lines), inline=False)
        else:
            embed.add_field(name="📦 Loot", value="Nothing dropped.", inline=False)

        if quest_lines:
            embed.add_field(name="📜 Quest Progress", value="\n".join(quest_lines), inline=False)

        # Milestone updates from combat outcomes.
        if interaction.guild_id:
            try:
                from services.milestones.milestone_service import MilestoneService
                ms = MilestoneService(self.bot.db)
                completed = []
                completed.extend(
                    await ms.increment(
                        interaction.guild_id,
                        "kills_total",
                        1,
                        source="combat_kill",
                        actor_id=interaction.user.id,
                    )
                )
                if session.is_boss:
                    completed.extend(
                        await ms.increment(
                            interaction.guild_id,
                            "boss_kills",
                            1,
                            source="combat_boss_kill",
                            actor_id=interaction.user.id,
                        )
                    )
                if gold_earned > 0:
                    completed.extend(
                        await ms.increment(
                            interaction.guild_id,
                            "gold_earned",
                            gold_earned,
                            source="combat_gold",
                            actor_id=interaction.user.id,
                        )
                    )
                if xp_result.get("levels_gained", 0) > 0:
                    completed.extend(
                        await ms.increment(
                            interaction.guild_id,
                            "levels_gained",
                            int(xp_result["levels_gained"]),
                            source="level_up",
                            actor_id=interaction.user.id,
                        )
                    )

                if completed:
                    lines = []
                    for c in completed:
                        reward = c.get("reward", {})
                        reward_label = reward.get("label", reward.get("type", "reward"))
                        lines.append(
                            f"• **{c['title']}** Tier {c['tier']} reached ({c['target']:,}) — {reward_label}"
                        )
                    embed.add_field(
                        name="🏁 Server Milestones",
                        value="\n".join(lines[:4]),
                        inline=False,
                    )
                    await ms.announce_completions(self.bot, interaction.guild_id, completed)
            except Exception:
                pass

        # Clear combat status on victory
        await self.bot.db.execute(
            "UPDATE characters SET combat_status='idle' WHERE id=$1",
            char["id"],
        )

        # Edit existing message instead of sending new one (saves API call)
        if msg:
            try:
                await msg.edit(embed=embed, view=None)
                return
            except Exception:
                pass
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _defeat(self, interaction, char, player: Combatant, msg=None):
        revive_hp = max(1, char["max_hp"] // 5)
        await self.bot.db.execute(
            "UPDATE characters SET current_hp=$2, combat_status='idle' WHERE id=$1",
            char["id"], revive_hp,
        )
        embed = discord.Embed(
            title="💀 Defeated!",
            description=(
                "You have been slain. You revive at the graveyard with **20% HP**.\n\n"
                "**Recovery tips:**\n"
                "• Use `/rest` to fully recover (60s cooldown)\n"
                "• Use a **Health Potion** from your inventory\n"
                "• Fight weaker enemies to build up"
            ),
            color=0xFF0000,
        )
        # Edit existing message instead of sending new one (saves API call)
        if msg:
            try:
                await msg.edit(embed=embed, view=None)
                return
            except Exception:
                pass
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _fled(self, interaction, char, player: Combatant, msg=None):
        """Handle successful flee — no death penalty, keep current HP."""
        await self.char_svc.sync_combat_hp(char["id"], player.current_hp, player.current_res)
        embed = discord.Embed(
            title="🏃 Escaped!",
            description="You fled from combat. Your HP is unchanged.",
            color=0x88AAFF,
        )
        if msg:
            try:
                await msg.edit(embed=embed, view=None)
                return
            except Exception:
                pass
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /rest ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="rest", description="Rest to fully recover HP and mana")
    async def rest(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "rest"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character found.")

        cd = await self.char_svc.on_cooldown(char["id"], "rest")
        if cd:
            return await interaction.followup.send(f"⏳ Rest again in **{int(cd)}s**.", ephemeral=True)

        await self.char_svc.full_restore(char["id"])
        await self.char_svc.set_cooldown(char["id"], "rest", Settings.REST_COOLDOWN)

        cls = CLASSES[char["class"]]
        res_name = {"mana": "💙 Mana", "energy": "⚡ Energy", "rage": "🔴 Rage"}.get(cls.resource, "🔋 Resource")
        
        embed = discord.Embed(
            title="💤 Rested",
            description=f"**{char['name']}** rests and recovers fully.",
            color=0x4488FF,
        )
        embed.add_field(name="❤️ HP", value=f"**{char['max_hp']:,}/{char['max_hp']:,}**", inline=True)
        if char["max_res"] > 0:
            embed.add_field(name=res_name, value=f"**{char['max_res']:,}/{char['max_res']:,}**", inline=True)
        embed.set_footer(text=f"Rest cooldown: {Settings.REST_COOLDOWN}s")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /combat_status ────────────────────────────────────────────────────────────

    @app_commands.command(name="combat_status", description="Check your current combat status")
    async def combat_status(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character found.", ephemeral=True)

        from services.combat.activity_combat import ACTIVE_ACTIVITY

        status = char["combat_status"]
        if status == "in_combat":
            # Check if there's actually an active combat session
            channel_has_combat = interaction.channel_id in ACTIVE
            activity_has_combat = interaction.user.id in ACTIVE_ACTIVITY
            if not channel_has_combat and not activity_has_combat:
                # Stuck in combat - clear it
                await self.bot.db.execute(
                    "UPDATE characters SET combat_status='idle' WHERE id=$1",
                    char["id"],
                )
                embed = discord.Embed(
                    title="⚔️ Combat Status",
                    description="You were stuck in combat status (no active fight).\n**Status cleared!** You can now use commands again.",
                    color=0x00FF00,
                )
            elif activity_has_combat:
                embed = discord.Embed(
                    title="⚔️ Combat Status",
                    description="You are in combat in the **Activity** (Embedded App). Continue there or flee.",
                    color=0xFF4444,
                )
            else:
                embed = discord.Embed(
                    title="⚔️ Combat Status",
                    description="You are currently **in combat**.\nUse `/fight` to continue or flee from the fight.",
                    color=0xFF4444,
                )
        else:
            embed = discord.Embed(
                title="⚔️ Combat Status",
                description=f"Status: **{status.title()}**\nYou are not in combat.",
                color=0x00FF00,
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CombatCog(bot))
