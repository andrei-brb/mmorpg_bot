# TODO: Party Healing & Multi-Player Dungeon Combat

## ✅ Completed
- [x] Fixed ability targeting system (`all_allies`, `all_enemies`, etc.)
- [x] Updated dungeon combat to include all party members in CombatSession
- [x] Updated combat embed to show all party members' HP/resource bars
- [x] Updated all `use_ability()` calls to pass session parameter

## 🔲 Still To Do / Improvements

### Testing & Verification
- [ ] Test `circle_of_healing` ability in party dungeon - verify it heals all party members
- [ ] Test `heal` ability (self-heal) works in party context
- [ ] Test other healing abilities (`prayer_of_mending`, `guardian_spirit`) in party
- [ ] Verify combat embed shows all party members correctly
- [ ] Test with 2-4 party members to ensure scaling works

### Combat Flow Improvements
- [ ] **Turn Order**: Currently only command invoker gets interactive UI - consider:
  - Option A: All party members get their own combat UI (separate messages)
  - Option B: Rotate turns, each player acts in sequence
  - Option C: Keep current (invoker controls, others auto-attack)
- [ ] **Party Member Death**: Handle when party members die:
  - Remove from combat session
  - Show death message
  - Handle party wipe scenario
- [ ] **HP/Resource Sync**: After combat, sync HP/resource for ALL party members (currently only syncs command invoker)
  - Update `_dungeon_victory()` to sync all participants
  - Update `_dungeon_defeat()` to sync all participants

### Reward Distribution
- [ ] **XP Distribution**: Currently only command invoker gets XP - distribute to all party members
- [ ] **Gold Distribution**: Currently only command invoker gets gold - distribute to all party members
- [ ] **Loot Distribution**: Currently only command invoker gets loot - consider:
  - Option A: All party members get loot
  - Option B: Loot goes to party leader
  - Option C: Need/greed system

### UI/UX Improvements
- [ ] **Party Status**: Show clearer party member status (alive/dead, HP%, etc.)
- [ ] **Ability Descriptions**: Update ability tooltips to clarify party vs solo usage
- [ ] **Combat Log**: Make it clearer when party members are healed by `circle_of_healing`
- [ ] **Turn Indicators**: Show whose turn it is in party combat

### Edge Cases & Bugs
- [ ] Handle party member leaving mid-combat
- [ ] Handle party member disconnecting during dungeon
- [ ] Verify enemy targeting works correctly with multiple players (threat system)
- [ ] Test boss abilities that target multiple players
- [ ] Verify `all_enemies` abilities work correctly (e.g., `whirlwind`, `multi_shot`)

### Future Enhancements
- [ ] **Role-Based Abilities**: Make tank abilities generate threat for party
- [ ] **Support Abilities**: Add buff abilities that target party members
- [ ] **Party Buffs**: Implement party-wide buffs (e.g., "Blessing of Kings")
- [ ] **Resurrection**: Add ability to revive dead party members
- [ ] **Party Roles**: Assign roles (tank, healer, DPS) and show in UI

## Notes
- Current implementation: Only command invoker gets interactive combat UI
- Other party members auto-attack each turn
- All party members are included in combat session for healing/buff targeting
- Enemy level scales based on average party level

## Testing Checklist
1. Create party with 2+ members
2. Start dungeon
3. Use `circle_of_healing` - verify all members get healed
4. Check combat embed shows all party members
5. Verify rewards are distributed (or note that they're not yet)
6. Test party member death scenario
7. Test party member leaving mid-combat
