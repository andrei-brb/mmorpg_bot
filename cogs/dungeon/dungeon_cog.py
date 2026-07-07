"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         cogs/dungeon/dungeon_cog.py — /dungeon commands                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from typing import Optional, List
from uuid import UUID

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import DUNGEONS, Settings
from services.character.character_service import CharacterService
from services.combat.combat_engine import CombatEngine, CombatSession, Combatant
from services.dungeon.dungeon_service import DungeonService

log = logging.getLogger("cog.dungeon")


# ── Dropdown Views ──────────────────────────────────────────────────────────────

class _DungeonSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.chosen = None
        self.add_item(_DungeonSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=1)
    async def cancel(self, interaction: discord.Interaction, _):
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None, embed=None)

class _DungeonSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for key, dungeon in DUNGEONS.items():
            options.append(
                discord.SelectOption(
                    label=f"{dungeon.emoji} {dungeon.name}",
                    value=key,
                    description=f"Level {dungeon.level_req}+ • {dungeon.floors} floors"
                )
            )
        super().__init__(placeholder="Select a dungeon…", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _DungeonSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
        
        view.chosen = self.values[0]
        view.stop()  # Stop FIRST so view.wait() returns immediately
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass  # Defer failure is non-critical


def _make_player(char, stats) -> Combatant:
    """Helper to create player combatant (same as combat_cog)."""
    from config.settings import CLASSES
    
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


def _make_enemy(enemy_key: str, level: int) -> Combatant:
    """Helper to create enemy combatant (similar to combat_cog)."""
    from config.settings import ENEMIES, Settings
    from uuid import uuid4
    
    tmpl = ENEMIES.get(enemy_key)
    if not tmpl:
        tmpl = ENEMIES["kobold"]  # Fallback
    
    scale = 1 + level * 0.06
    hp = int(tmpl.hp_base * scale)
    if tmpl.is_boss:
        # Dungeons are intended to be harder than open‑world, but slightly below
        # full raid tuning. Keep using BOSS_HP_SCALE, but you can lower it here
        # independently later if needed.
        hp = int(hp * Settings.BOSS_HP_SCALE)
    
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


class DungeonCog(commands.Cog, name="Dungeon"):
    def __init__(self, bot):
        self.bot = bot
        self.engine = CombatEngine()
        self.char_svc: CharacterService = None
        self.dungeon_svc: DungeonService = None
        self.active_runs: dict[UUID, CombatSession] = {}  # run_id -> combat session

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.dungeon_svc = DungeonService(self.bot.db)
        # Clean up any orphaned dungeon runs from previous bot sessions
        await self.bot.db.execute(
            "UPDATE dungeon_runs SET is_active=FALSE, outcome='abandoned' WHERE is_active=TRUE"
        )
        await self.bot.db.execute("UPDATE characters SET in_dungeon=FALSE WHERE in_dungeon=TRUE")
        log.info("Cleaned up orphaned dungeon runs")

    dungeon = app_commands.Group(name="dungeon", description="Dungeon exploration commands")

    @dungeon.command(name="list", description="List available dungeons")
    async def list_dungeons(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "dungeon"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🏰 Available Dungeons", color=0x8B4513)
        
        char = await self.char_svc.get_character(interaction.user.id)
        char_level = char["level"] if char else 1
        
        for key, dungeon in DUNGEONS.items():
            can_enter = char_level >= dungeon.level_req if char else False
            status = "✅" if can_enter else f"❌ (Level {dungeon.level_req}+)"
            
            embed.add_field(
                name=f"{dungeon.emoji} {dungeon.name} {status}",
                value=(
                    f"{dungeon.description}\n"
                    f"**Floors:** {dungeon.floors} | "
                    f"**Level Req:** {dungeon.level_req}+ | "
                    f"**XP/Flor:** {dungeon.xp_reward:,}"
                ),
                inline=False,
            )
        
        await interaction.followup.send(embed=embed)

    @dungeon.command(name="enter", description="Enter a dungeon (solo)")
    @app_commands.describe(dungeon="Choose a dungeon from the list")
    async def enter_dungeon(self, interaction: discord.Interaction, dungeon: Optional[str] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "dungeon"):
            return
        import time as _time
        t0 = _time.monotonic()
        if not interaction.response.is_done():
            await interaction.response.defer()
        log.info(f"[DUNGEON] defer took {_time.monotonic()-t0:.2f}s")

        char = await self.char_svc.get_character(interaction.user.id)
        log.info(f"[DUNGEON] get_character took {_time.monotonic()-t0:.2f}s")
        if not char:
            return await interaction.followup.send("❌ No character. Use `/character create`.")
        
        if char["combat_status"] == "in_combat":
            return await interaction.followup.send("⚔️ You're already in combat!")
        
        if char["in_dungeon"]:
            return await interaction.followup.send("🏰 You're already in a dungeon! Use `/dungeon leave` first.")
        
        # If no dungeon provided, show available list (no dropdown wait)
        if dungeon is None:
            lines = []
            for key, d in DUNGEONS.items():
                can = "✅" if char["level"] >= d.level_req else f"❌ Lv{d.level_req}+"
                lines.append(f"{d.emoji} **{d.name}** ({can}) — `/dungeon enter dungeon:{key}`")
            embed = discord.Embed(
                title="🏰 Choose a Dungeon",
                description="Use autocomplete: type `/dungeon enter` and pick one!\n\n" + "\n".join(lines),
                color=0x8B4513,
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        dungeon_config = DUNGEONS.get(dungeon)
        if not dungeon_config:
            return await interaction.followup.send(f"❌ Unknown dungeon. Use `/dungeon list` to see available dungeons.")
        
        if char["level"] < dungeon_config.level_req:
            return await interaction.followup.send(
                f"❌ This dungeon requires level **{dungeon_config.level_req}**. You are level **{char['level']}**."
            )
        
        # Create solo run
        run_id = await self.dungeon_svc.create_run(dungeon, char["id"], is_solo=True)
        log.info(f"[DUNGEON] create_run took {_time.monotonic()-t0:.2f}s")
        if not run_id:
            return await interaction.followup.send("❌ Failed to create dungeon run.")
        
        # Start first floor combat
        await self._start_floor_combat(interaction, run_id, dungeon_config, char)
        log.info(f"[DUNGEON] total enter took {_time.monotonic()-t0:.2f}s")

    @dungeon.command(name="create", description="Create a party dungeon")
    @app_commands.describe(dungeon="Choose a dungeon from the list")
    async def create_party(self, interaction: discord.Interaction, dungeon: Optional[str] = None):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        
        if char["in_dungeon"]:
            return await interaction.followup.send("🏰 You're already in a dungeon!")
        
        # If no dungeon provided, show list instead of dropdown
        if dungeon is None:
            lines = []
            for key, d in DUNGEONS.items():
                can = "✅" if char["level"] >= d.level_req else f"❌ Lv{d.level_req}+"
                lines.append(f"{d.emoji} **{d.name}** ({can}) — use `/dungeon create dungeon:{key}`")
            embed = discord.Embed(
                title="🏰 Choose a Dungeon",
                description="Use autocomplete: type `/dungeon create` and pick one!\n\n" + "\n".join(lines),
                color=0x8B4513,
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        dungeon_config = DUNGEONS.get(dungeon)
        if not dungeon_config:
            return await interaction.followup.send("❌ Unknown dungeon.")
        
        if char["level"] < dungeon_config.level_req:
            return await interaction.followup.send(f"❌ Requires level {dungeon_config.level_req}.")
        
        run_id = await self.dungeon_svc.create_run(dungeon, char["id"], is_solo=False)
        if not run_id:
            return await interaction.followup.send("❌ Failed to create party.")
        
        embed = discord.Embed(
            title=f"🏰 Party Created: {dungeon_config.emoji} {dungeon_config.name}",
            description=f"**Leader:** {char['name']}\n**Members:** 1/{Settings.MAX_PARTY_SIZE}",
            color=Settings.COLORS["success"],
        )
        embed.add_field(
            name="📋 Commands",
            value=(
                f"`/dungeon invite @player` — Invite someone\n"
                f"`/dungeon start` — Begin dungeon (when ready)\n"
                f"`/dungeon leave` — Leave party"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Run ID: {str(run_id)[:8]}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @enter_dungeon.autocomplete("dungeon")
    @create_party.autocomplete("dungeon")
    async def dungeon_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for dungeon names — lightweight, single DB query."""
        current = (current or "").lower()
        
        # Quick level lookup (single column, no joins)
        char_level = await self.bot.db.fetchval(
            "SELECT level FROM characters WHERE discord_id=$1", interaction.user.id
        ) or 1
        
        choices = []
        for key, dungeon in DUNGEONS.items():
            if current in key.lower() or current in dungeon.name.lower():
                status = "✅" if char_level >= dungeon.level_req else f"Lv {dungeon.level_req}+"
                choices.append(
                    app_commands.Choice(
                        name=f"{dungeon.emoji} {dungeon.name} ({status})",
                        value=key
                    )
                )
        
        return choices[:25]

    @dungeon.command(name="invite", description="Invite a player to your dungeon party")
    @app_commands.describe(member="Player to invite")
    async def invite_player(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        
        run = await self.dungeon_svc.get_active_run(char["id"])
        if not run:
            return await interaction.followup.send("❌ You're not in a dungeon party. Use `/dungeon create`.")
        
        # Check if leader
        is_leader = any(p["id"] == char["id"] and p.get("role") == "leader" for p in run["participants"])
        if not is_leader:
            return await interaction.followup.send("❌ Only the party leader can invite players.")
        
        target_char = await self.char_svc.get_character(member.id)
        if not target_char:
            return await interaction.followup.send(f"❌ {member.display_name} has no character.")
        
        if target_char["in_dungeon"]:
            return await interaction.followup.send(f"❌ {member.display_name} is already in a dungeon.")
        
        success = await self.dungeon_svc.add_participant(run["id"], target_char["id"])
        if not success:
            return await interaction.followup.send("❌ Failed to add player (party full or already in party).")
        
        await interaction.followup.send(f"✅ Invited **{target_char['name']}** to the party!")
        
        # Notify invited player
        try:
            await member.send(f"🏰 **{char['name']}** invited you to a dungeon party! Use `/dungeon join` to accept.")
        except:
            pass  # DMs disabled

    @dungeon.command(name="join", description="Join a dungeon party")
    async def join_party(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        
        if char["in_dungeon"]:
            return await interaction.followup.send("🏰 You're already in a dungeon!")
        
        # For now, join the first available party (could be improved with party codes)
        # In a real implementation, you'd use party codes or invites
        await interaction.followup.send(
            "❌ Party joining by code not yet implemented. Use `/dungeon invite` from the party leader."
        )

    @dungeon.command(name="start", description="Start the dungeon (party leader only)")
    async def start_dungeon(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        
        run = await self.dungeon_svc.get_active_run(char["id"])
        if not run:
            return await interaction.followup.send("❌ You're not in a dungeon party.")
        
        # Check if leader
        is_leader = any(p["id"] == char["id"] and p.get("role") == "leader" for p in run["participants"])
        if not is_leader:
            return await interaction.followup.send("❌ Only the party leader can start the dungeon.")
        
        dungeon_config = DUNGEONS.get(run["dungeon_key"])
        if not dungeon_config:
            return await interaction.followup.send("❌ Invalid dungeon configuration.")
        
        # Start first floor
        await self._start_floor_combat(interaction, run["id"], dungeon_config, char)

    @dungeon.command(name="status", description="Check your dungeon status")
    async def dungeon_status(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        
        if not char["in_dungeon"]:
            return await interaction.followup.send("❌ You're not in a dungeon.")
        
        run = await self.dungeon_svc.get_active_run(char["id"])
        if not run:
            return await interaction.followup.send("❌ Dungeon run not found.")
        
        dungeon_config = DUNGEONS.get(run["dungeon_key"])
        
        embed = discord.Embed(
            title=f"🏰 {dungeon_config.emoji} {dungeon_config.name}",
            description=f"**Floor:** {run['current_floor']}/{run['total_floors']}",
            color=0x8B4513,
        )
        
        if len(run["participants"]) > 1:
            members = "\n".join([f"• {p['name']} (Level {p['level']})" for p in run["participants"]])
            embed.add_field(name="👥 Party", value=members, inline=False)
        
        await interaction.followup.send(embed=embed)

    @dungeon.command(name="leave", description="Leave the current dungeon")
    async def leave_dungeon(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")

        if not char["in_dungeon"]:
            return await interaction.followup.send("❌ You're not in a dungeon.")

        await self.dungeon_svc.leave_run(char["id"])
        await interaction.followup.send("✅ Left the dungeon.")

    @dungeon.command(name="debug_party", description="Debug party information (admin)")
    async def debug_party(self, interaction: discord.Interaction):
        """Debug command to check party state."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.")

        run = await self.dungeon_svc.get_active_run(char["id"])
        if not run:
            return await interaction.followup.send("❌ No active dungeon run.")

        # Debug info
        debug_text = f"**Run ID:** `{run['id']}`\n"
        debug_text += f"**Dungeon:** {run['dungeon_key']}\n"
        debug_text += f"**Active:** {run['is_active']}\n"
        debug_text += f"**Floor:** {run['current_floor']}/{run['total_floors']}\n"
        debug_text += f"**Participants:** {len(run['participants'])}\n\n"
        
        for i, p in enumerate(run['participants']):
            debug_text += f"{i+1}. `{p['id']}` - {p['name']} (Lv.{p['level']}) - Role: `{p['role']}`\n"
        
        # Check if current user is leader
        is_leader = any(p["id"] == char["id"] and p.get("role") == "leader" for p in run["participants"])
        debug_text += f"\n**You are leader:** {is_leader}\n"
        debug_text += f"**Your character ID:** `{char['id']}`"
        
        await interaction.followup.send(f"🔍 **Debug Info:**\n{debug_text}", ephemeral=True)

    async def _start_floor_combat(self, interaction: discord.Interaction, run_id: UUID, dungeon_config, char):
        """Start a dungeon floor combat."""
        import time as _time
        t0 = _time.monotonic()
        
        run = await self.dungeon_svc.get_run(run_id)
        log.info(f"[DUNGEON] get_run took {_time.monotonic()-t0:.2f}s")
        floor = run["current_floor"]
        
        # Get enemies for this floor
        enemy_key = dungeon_config.enemies_per_floor[(floor - 1) % len(dungeon_config.enemies_per_floor)]
        is_boss = floor == dungeon_config.floors  # Last floor is boss
        
        if is_boss:
            boss_key = dungeon_config.floor_bosses[-1]
            enemy_key = boss_key
        
        # Get all party members and create combatants
        participants = run.get("participants", [])
        player_combatants = []
        levels = []
        
        for participant in participants:
            p_char = await self.char_svc.get_by_id(participant["id"])
            if not p_char:
                continue
            p_stats = await self.char_svc.total_stats(participant["id"])
            from services.combat.activity_combat import _make_player as _make_player_with_talents
            from services.talents.talent_combat import fetch_talent_effects

            talent_fx = await fetch_talent_effects(
                self.bot.db,
                participant["id"],
                str(p_char.get("class") or ""),
                p_char.get("specialization"),
            )
            p_combatant = _make_player_with_talents(dict(p_char), p_stats, talent_fx)
            player_combatants.append(p_combatant)
            levels.append(p_char["level"])
        
        log.info(f"[DUNGEON] participants setup took {_time.monotonic()-t0:.2f}s")
        
        # Use average level for enemy scaling
        avg_level = sum(levels) // len(levels) if levels else char["level"]
        enemy_c = _make_enemy(enemy_key, avg_level)
        
        session = CombatSession(
            session_id=run_id,
            players=player_combatants,
            enemies=[enemy_c],
            is_boss=is_boss,
            enemy_key=enemy_key,
            zone_key=dungeon_config.key,
            apply_lore_gates=False,
        )
        
        self.active_runs[run_id] = session
        
        embed = discord.Embed(
            title=f"🏰 {dungeon_config.emoji} {dungeon_config.name} — Floor {floor}/{dungeon_config.floors}",
            description=f"**Enemy:** {enemy_c.name}",
            color=0x8B4513,
        )
        
        # Use combat cog's _run method but handle dungeon completion
        await self._run_dungeon_combat(interaction, session, char, run_id, dungeon_config, msg=None)

    async def _run_dungeon_combat(self, interaction, session: CombatSession, char: dict, run_id: UUID, dungeon_config, msg=None):
        """Run dungeon combat with floor progression."""
        from cogs.combat.combat_cog import AbilityView, _build_embed
        from config.settings import CLASSES, Settings
        from services.combat.combat_engine import ABILITIES
        
        char_id = char["id"]
        log_lines: list[str] = []

        # Cache run info once — floor doesn't change mid-combat
        run_info = await self.dungeon_svc.get_run(run_id)
        floor_title = f"🏰 {dungeon_config.emoji} {dungeon_config.name} — Floor {run_info['current_floor']}/{dungeon_config.floors}"

        # Cache class info once
        cls = CLASSES[char["class"]]
        cost_mult = getattr(Settings, "RESOURCE_COST_MULT", {}).get(char["class"], 1.0)

        while not session.over:
            session.turn += 1
            
            # Process all players' turns
            enemy = session.alive_enemies[0] if session.alive_enemies else None
            if not enemy:
                break
                
            for player in session.alive_players:
                if session.over:
                    break
                    
                # Only show UI for the command invoker
                if player.char_id and str(player.char_id) == str(char["id"]):
                    ticks = self.engine.tick_turn(player)
                    if ticks:
                        log_lines.extend(ticks)
                    if player.is_dead:
                        continue

                    # Build UI — no extra DB calls needed, we have the player combatant already
                    view = AbilityView(char, player, owner_id=interaction.user.id)
                    embed = _build_embed(session, log_lines)
                    embed.title = floor_title

                    if msg:
                        await msg.edit(embed=embed, view=view)
                    else:
                        msg = await interaction.followup.send(embed=embed, view=view, wait=True, ephemeral=True)

                    await view.wait()

                    # Flee
                    if view.fled:
                        flee_roll = Settings.FLEE_BASE_CHANCE + player.dodge_chance * 0.01
                        if random.random() < flee_roll:
                            log_lines.append(f"🏃 **{player.name}** escaped!")
                            await self.dungeon_svc.leave_run(char_id)
                            break
                        else:
                            log_lines.append("🚫 You couldn't flee!")
                    else:
                        ab_key = view.chosen or "auto_attack"
                        ab = ABILITIES.get(ab_key, ABILITIES["auto_attack"])
                        eff_cost = int(ab.cost * cost_mult) if ab.cost else 0

                        if ab.cost_type in ("mana", "energy", "rage") and player.current_res < eff_cost:
                            log_lines.append(f"❌ Not enough {ab.cost_type} for **{ab.name}**!")
                        elif ab_key in player.ability_cooldowns:
                            log_lines.append(f"⏳ **{ab.name}** is on cooldown!")
                        else:
                            if ab.cost_type in ("mana", "energy", "rage") and eff_cost:
                                player.current_res = max(0, player.current_res - eff_cost)
                            enemy = session.alive_enemies[0] if session.alive_enemies else None
                            results = self.engine.use_ability(ab_key, player, [enemy] if enemy else [], session=session)
                            for r in results:
                                log_lines.append(r.narrative)
                            session.log.extend(results)
                            # Ability mastery progression (lightweight).
                            try:
                                await self.char_svc.award_ability_mastery_xp(char["id"], ab_key, 1)
                            except Exception:
                                pass
                else:
                    # Other party members auto-attack
                    ticks = self.engine.tick_turn(player)
                    if ticks:
                        log_lines.extend(ticks)
                    if not player.is_dead and session.alive_enemies:
                        enemy = session.alive_enemies[0]
                        results = self.engine.use_ability("auto_attack", player, [enemy], session=session)
                        for r in results:
                            log_lines.append(r.narrative)
                        session.log.extend(results)

            if session.over:
                break

            # Enemy turn
            if not session.alive_enemies:
                break
            enemy = session.alive_enemies[0]
            e_ticks = self.engine.tick_turn(enemy)
            if e_ticks:
                log_lines.extend(e_ticks)

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

            if msg:
                await msg.edit(embed=_build_embed(session, log_lines), view=None)

        # Combat ended
        player = session.players[0]

        if session.players_won:
            await self._dungeon_victory(interaction, session, char, player, run_id, dungeon_config, msg)
        else:
            await self._dungeon_defeat(interaction, char, player, run_id, msg)

    async def _dungeon_victory(self, interaction, session, char, player, run_id: UUID, dungeon_config, msg=None):
        """Handle dungeon floor victory."""
        from services.character.inventory_service import InventoryService
        from config.settings import Settings
        
        inv_svc = InventoryService(self.bot.db)
        
        run = await self.dungeon_svc.get_run(run_id)
        floor = run["current_floor"]
        
        # Calculate rewards (multiplied for dungeons)
        base_xp = dungeon_config.xp_reward * Settings.DUNGEON_XP_MULTIPLIER
        base_gold = random.randint(*dungeon_config.gold_reward) * Settings.DUNGEON_GOLD_MULTIPLIER
        
        server_cfg = await self.bot.db.fetchrow(
            "SELECT xp_multiplier, gold_multiplier FROM server_config WHERE server_id=$1",
            interaction.guild_id,
        )
        xp_mult = server_cfg["xp_multiplier"] if server_cfg else 1.0
        gold_mult = server_cfg["gold_multiplier"] if server_cfg else 1.0
        
        # Distribute rewards to every party member in the session: full XP each,
        # gold split evenly, one loot roll each (two on boss floors), HP/resource synced.
        participants = {str(p["id"]): p for p in run.get("participants", [])}
        members = [p for p in session.players if p.char_id is not None]
        n = max(1, len(members))
        gold_each = max(1, int(base_gold * gold_mult) // n)

        level_up_lines = []
        loot_lines = []
        for member in members:
            m_id = member.char_id
            m_info = participants.get(str(m_id), {})
            m_name = m_info.get("name") or member.name
            m_level = int(m_info.get("level") or char["level"])

            m_xp = await self.char_svc.award_xp(m_id, int(base_xp), xp_mult)
            await self.char_svc.add_gold(m_id, gold_each, "dungeon_reward")
            await self.char_svc.sync_combat_hp(m_id, member.current_hp, member.current_res)
            if m_xp.get("leveled_up"):
                level_up_lines.append(f"**{m_name}**: {m_xp['old_level']} → {m_xp['new_level']}")

            # Daily quest progress (non-blocking)
            try:
                from services.quest.daily_quest_service import DailyQuestService
                daily_svc = DailyQuestService(self.bot.db)
                daily_line = await daily_svc.record_event(self.char_svc, m_id, "kill")
                if session.is_boss:
                    daily_line = await daily_svc.record_event(self.char_svc, m_id, "boss") or daily_line
                if daily_line:
                    loot_lines.append(f"**{m_name}** — {daily_line}" if n > 1 else daily_line)
            except Exception:
                pass

            for _ in range(2 if session.is_boss else 1):  # Boss gives 2 loot rolls
                loot = await inv_svc.generate_loot(run["dungeon_key"], m_level, session.is_boss, char_id=m_id)
                if loot:
                    ok, _ = await inv_svc.add_item(
                        m_id, loot["template"]["id"], loot["rarity"], bonus=loot["bonus"]
                    )
                    if ok:
                        prefix = f"**{m_name}** — " if n > 1 else ""
                        loot_lines.append(f"✨ {prefix}{loot['template']['name']} ({loot['rarity']})")

        # Class mastery progression (victory-based; boss fights grant more).
        try:
            base_gain = 8 + (6 if session.is_boss else 0)
            await self.char_svc.award_class_mastery_xp(char["id"], char.get("class") or "", base_gain)
        except Exception:
            pass

        # Chance to refill health potion (35% dungeon)
        if random.random() < 0.35:
            ok, _ = await inv_svc.add_item(char["id"], "health_potion", "common", from_="combat_drop")
            if ok:
                loot_lines.append("🧪 **Health Potion** (refill)")
        
        embed = discord.Embed(
            title=f"✅ Floor {floor} Complete!",
            description=f"**{char['name']}** defeated {session.enemies[0].name}!",
            color=Settings.COLORS["success"],
        )
        gold_txt = f"{gold_each:,}" + (f" each ({n}-way split)" if n > 1 else "")
        embed.add_field(name="💰 Gold", value=gold_txt, inline=True)
        embed.add_field(name="⭐ XP", value=f"{int(base_xp * xp_mult):,}" + (" each" if n > 1 else ""), inline=True)

        if loot_lines:
            embed.add_field(name="📦 Loot", value="\n".join(loot_lines)[:1024], inline=False)

        if level_up_lines:
            embed.add_field(
                name="🎉 LEVEL UP!",
                value="\n".join(level_up_lines),
                inline=False,
            )
        
        # Check if dungeon complete
        if floor >= dungeon_config.floors:
            # Edit existing message with victory, then send completion (only 1 extra API call)
            if msg:
                try:
                    await msg.edit(embed=embed, view=None)
                except Exception:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
            await self._complete_dungeon(interaction, run_id, dungeon_config, char)
        else:
            # Merge "floor complete" + "proceeding" into single embed edit (saves API calls)
            await self.dungeon_svc.advance_floor(run_id)
            embed.add_field(
                name="🏰 Next Floor",
                value=f"Proceeding to Floor {floor + 1}…",
                inline=False,
            )
            if msg:
                try:
                    await msg.edit(embed=embed, view=None)
                except Exception:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Refresh char data for next floor
            char_fresh = await self.char_svc.get_character(interaction.user.id)
            if char_fresh:
                char = dict(char_fresh)
            
            # Start next floor combat — pass msg=None since we start a new combat message
            await self._start_floor_combat(interaction, run_id, dungeon_config, char)

    async def _complete_dungeon(self, interaction, run_id: UUID, dungeon_config, char):
        """Handle dungeon completion."""
        await self.dungeon_svc.complete_run(run_id, "victory")
        
        # Check dungeon achievements
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        participants = await self.dungeon_svc.get_run(run_id)
        is_solo = len(participants.get("participants", [])) == 1 if participants else False
        await ach_svc.check_and_award(char["id"], "dungeon_complete", {"is_solo": is_solo})
        
        embed = discord.Embed(
            title=f"🏆 Dungeon Complete!",
            description=f"**{dungeon_config.emoji} {dungeon_config.name}** cleared!",
            color=Settings.COLORS["reward"],
        )
        embed.add_field(
            name="✨ Bonus Rewards",
            value="You've earned bonus XP and gold for completing the dungeon!",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _dungeon_defeat(self, interaction, char, player, run_id: UUID, msg=None):
        """Handle dungeon defeat."""
        # Revive and clear combat state for ALL participants, not just the invoker.
        await self.bot.db.execute(
            """
            UPDATE characters SET current_hp = GREATEST(1, max_hp / 5), combat_status='idle'
            WHERE id IN (SELECT character_id FROM dungeon_participants WHERE run_id=$1)
            """,
            run_id,
        )
        await self.bot.db.execute(
            """
            UPDATE inventory SET durability = GREATEST(0, durability - $2)
            WHERE is_equipped=TRUE
              AND character_id IN (SELECT character_id FROM dungeon_participants WHERE run_id=$1)
            """,
            run_id, Settings.DURABILITY_LOSS_ON_DEFEAT,
        )

        await self.dungeon_svc.complete_run(run_id, "defeat")

        embed = discord.Embed(
            title="💀 Defeated!",
            description=(
                "Your party has been slain in the dungeon. Everyone revives at the entrance.\n"
                f"Equipped gear lost **{Settings.DURABILITY_LOSS_ON_DEFEAT} durability** — "
                "repair it with `/blacksmith repair`.\n\n"
                "**Recovery tips:**\n"
                "• Use `/rest` to fully recover\n"
                "• Use a **Health Potion** from your inventory\n"
                "• Try again when you're stronger!"
            ),
            color=Settings.COLORS["error"],
        )
        # Edit existing message instead of sending new one (saves API call)
        if msg:
            try:
                await msg.edit(embed=embed, view=None)
                return
            except Exception:
                pass
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DungeonCog(bot))
