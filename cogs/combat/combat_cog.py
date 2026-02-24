"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              cogs/combat/combat_cog.py — /fight /rest commands             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from typing import Dict, List, Optional
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import CLASSES, ENEMIES, ZONES, RARITIES, Settings
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.combat.combat_engine import (
    ABILITIES, CombatEngine, CombatResult, CombatSession, Combatant
)

log = logging.getLogger("cog.combat")

# Channel-level lock: channel_id -> CombatSession
ACTIVE: Dict[int, CombatSession] = {}


def _make_enemy(key: str, char_level: int) -> Combatant:
    tmpl = ENEMIES.get(key, ENEMIES["kobold"])
    scale = 1 + char_level * 0.06
    hp = int(tmpl.hp_base * scale)
    if tmpl.is_boss:
        hp *= Settings.BOSS_HP_SCALE
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
    cls = CLASSES[char["class"]]
    return Combatant(
        id=str(char["id"]), name=char["name"],
        is_player=True, char_id=char["id"],
        current_hp=char["current_hp"], max_hp=char["max_hp"],
        current_res=char["current_res"], max_res=char["max_res"],
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
    def __init__(self, char, combatant: Combatant, owner_id: int = None):
        super().__init__(timeout=Settings.COMBAT_TIMEOUT_SECONDS)
        self.chosen   = None
        self.fled     = False
        self.owner_id = owner_id

        cls = CLASSES[char["class"]]
        keys = ["auto_attack"] + list(cls.starter_abilities)
        if char.get("specialization"):
            from config.settings import SPECIALIZATIONS
            spec = SPECIALIZATIONS.get(char["specialization"])
            if spec:
                keys.extend(spec.bonus_abilities)

        options = []
        cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
        for key in dict.fromkeys(keys):  # deduplicate, preserve order
            ab = ABILITIES.get(key)
            if not ab: continue
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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        log.info(f"[COMBAT LOCK] owner_id={self.owner_id}, clicker={interaction.user.id} ({interaction.user.display_name})")
        if self.owner_id and interaction.user.id != self.owner_id:
            log.info(f"[COMBAT LOCK] BLOCKED {interaction.user.display_name} from using {interaction.user.display_name}'s combat")
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
            hp = int(boss.hp_base * scale * Settings.BOSS_HP_SCALE)
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
            self.stop()  # Stop FIRST
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception as e:
                log.warning(f"Error deferring enemy selection: {e}")
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

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc  = InventoryService(self.bot.db)

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
        
        # Check if stuck in combat (status says in_combat but no active session)
        if char["combat_status"] == "in_combat":
            channel_has_combat = interaction.channel_id in ACTIVE
            if not channel_has_combat:
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
        enemy_c   = _make_enemy(enemy_key, char["level"])

        session = CombatSession(
            session_id=uuid4(),
            players=[player_c],
            enemies=[enemy_c],
            is_boss=is_boss,
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
            fresh = await self.char_svc.get_character(interaction.user.id)
            view  = AbilityView(dict(fresh), player, owner_id=interaction.user.id)
            embed = _build_embed(session, log_lines)

            if msg:
                await msg.edit(embed=embed, view=view)
            else:
                msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            await view.wait()

            # ── Flee ──────────────────────────────────────────────────────────
            if view.fled:
                flee_roll = Settings.FLEE_BASE_CHANCE + player.dodge_chance * 0.01
                if random.random() < flee_roll:
                    log_lines.append("🏃 You escaped!")
                    # Clear combat status on successful flee
                    await self.bot.db.execute(
                        "UPDATE characters SET combat_status='idle' WHERE id=$1",
                        char_id,
                    )
                    break
                else:
                    log_lines.append("🚫 You couldn't flee!")

            else:
                # ── Player action ─────────────────────────────────────────────
                ab_key = view.chosen or "auto_attack"
                ab = ABILITIES.get(ab_key, ABILITIES["auto_attack"])
                cls = CLASSES[char["class"]]
                cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)
                eff_cost = int(ab.cost * cost_mult) if ab.cost else 0

                # Resource check
                if ab.cost_type in ("mana", "energy", "rage") and player.current_res < eff_cost:
                    log_lines.append(f"❌ Not enough {ab.cost_type} for **{ab.name}**!")
                elif ab_key in player.ability_cooldowns:
                    log_lines.append(f"⏳ **{ab.name}** is on cooldown!")
                else:
                    if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
                        player.current_res = max(0, player.current_res - eff_cost)
                    results = self.engine.use_ability(ab_key, player, [enemy], session=session)
                    for r in results:
                        log_lines.append(r.narrative)
                    session.log.extend(results)

            if session.over: break

            # ── Enemy start-of-turn ───────────────────────────────────────────
            e_ticks = self.engine.tick_turn(enemy)
            if e_ticks: log_lines.extend(e_ticks)

            if not enemy.is_dead:
                if session.is_boss:
                    session.boss_phase = self.engine.boss_phase(enemy)
                e_ab, e_targets = self.engine.enemy_turn(
                    enemy, session.alive_players, session.is_boss, session.boss_phase
                )
                if e_targets:
                    e_results = self.engine.use_ability(e_ab, enemy, e_targets, session=session)
                    for r in e_results:
                        log_lines.append(r.narrative)
                    session.log.extend(e_results)

            # Update the embed with new log
            if msg:
                await msg.edit(embed=_build_embed(session, log_lines), view=None)

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

        if session.players_won:
            await self._victory(interaction, session, char, player, msg)
        else:
            await self._defeat(interaction, char, player, msg)

    async def _victory(self, interaction, session, char, player: Combatant, msg=None):
        server_cfg = await self.bot.db.fetchrow(
            "SELECT xp_multiplier, gold_multiplier FROM server_config WHERE server_id=$1",
            interaction.guild_id,
        )
        xp_mult   = server_cfg["xp_multiplier"]   if server_cfg else 1.0
        gold_mult = server_cfg["gold_multiplier"]  if server_cfg else 1.0

        rewards = self.engine.calculate_rewards(session, xp_mult, gold_mult)

        xp_result = await self.char_svc.award_xp(char["id"], rewards["xp"], xp_mult)
        await self.char_svc.add_gold(char["id"], rewards["gold"], "combat drop")
        await self.char_svc.sync_combat_hp(char["id"], player.current_hp, player.current_res)

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

        embed = discord.Embed(
            title="🏆 Victory!",
            description=f"You defeated **{session.enemies[0].name}**!",
            color=0x00FF7F,
        )
        embed.add_field(name="⚡ Rewards", value=f"+**{rewards['xp']:,}** XP  |  +**{rewards['gold']:,}**🪙", inline=False)

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
        
        status = char["combat_status"]
        if status == "in_combat":
            # Check if there's actually an active combat session
            channel_has_combat = interaction.channel_id in ACTIVE
            if not channel_has_combat:
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
