/**
 * Tabs.
 *
 * This keeps the CLASSIC tab list — players already know where things are — and
 * adds Camp at the front. An earlier draft collapsed everything into five
 * intent-shaped tabs; that reorganised muscle memory as well as the pixels,
 * which is a bigger change than was wanted here.
 *
 * Two treatments, deliberately:
 *
 *   REBUILT in Ember   Camp, Hero, Quests, Combat, Guild, Market, Arena,
 *                      Battle Pass, Realm
 *   SKINNED only       Explore, Forge — classic layout, Ember colours. Their
 *                      structure is good and stays; they just stop being
 *                      amber-on-black. Because it's a token override rather
 *                      than a fork, they inherit future classic changes free.
 *
 * Eleven tabs won't fit a phone bar, so four live in the bar and the rest in a
 * More sheet — the same shape the classic mobile shell already uses.
 */

export type EmberTab =
  | "camp"
  | "explore"
  | "combat"
  | "quests"
  | "hero"
  | "forge"
  | "guild"
  | "market"
  | "arena"
  | "pass"
  | "realm";

export type TabDef = {
  id: EmberTab;
  label: string;
  /** 24x24 stroke path. Drawn, not emoji, so it takes the active colour. */
  icon: string;
  hint: string;
  /** True for tabs that keep classic layout and only wear the Ember palette. */
  skinnedOnly?: boolean;
  /**
   * Level at which this tab appears. Absent means level 1.
   *
   * A new character used to land on eleven tabs at once, most of which lead
   * somewhere they cannot act: an empty guild, a market they cannot afford, an
   * arena that will kill them. Showing everything up front reads as "here is
   * how much you do not have" — and it wastes the only lever the game has for
   * making a level-up feel like something, which is giving you something new.
   *
   * Levels are set to the point where the tab has something real behind it,
   * not spaced arbitrarily. Nothing that blocks the core loop is ever gated —
   * Camp, Explore, Combat, Quests and Hero are all available from the start.
   */
  unlockLevel?: number;
  /** One line shown while locked. Says what is behind it, not just the level. */
  lockedHint?: string;
};

/** The bottom bar. */
export const PRIMARY_TABS: TabDef[] = [
  {
    id: "camp",
    label: "Camp",
    hint: "What's waiting for you",
    icon: "M12 2c.5 3.5-1.5 4.5-3 6.5C7.4 10.6 6 12.4 6 15a6 6 0 0 0 12 0c0-2.2-1-3.6-2-5-.6 1-1.2 1.6-2 2 .5-3.5-1-6.5-2-10Z",
  },
  {
    id: "explore",
    label: "Explore",
    hint: "Zones and encounters",
    skinnedOnly: true,
    icon: "M9 4 3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4Zm0 0v13m6-10.5v13",
  },
  {
    id: "combat",
    label: "Combat",
    hint: "Fight and dungeons",
    icon: "M14.5 3.5 20 9m0-5.5L14.5 9M6 21l6-6m-6 0 3 3m-6-9 9 9M4 4l7 7",
  },
  {
    id: "quests",
    label: "Quests",
    hint: "Story and objectives",
    icon: "M6 3h9l4 4v14H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm9 0v4h4M9 12h6M9 16h4",
  },
];

/** Everything else, in the More sheet. Grouped the way the classic drawer is. */
export const MORE_GROUPS: { label: string; tabs: TabDef[] }[] = [
  {
    label: "Character",
    tabs: [
      {
        id: "hero",
        label: "Hero",
        hint: "Gear, stats, bag",
        icon: "M12 3 5 6v5.5c0 4.3 2.9 8.3 7 9.5 4.1-1.2 7-5.2 7-9.5V6l-7-3Z",
      },
      {
        id: "forge",
        unlockLevel: 5,
        lockedHint: "Crafting is worth opening once you have materials and gold to spend.",
        label: "Forge",
        hint: "Craft and repair",
        skinnedOnly: true,
        icon: "M14 6 18 2l4 4-4 4m-4-4L3 17v4h4L18 10M9 12l3 3",
      },
    ],
  },
  {
    label: "Social",
    tabs: [
      {
        id: "guild",
        unlockLevel: 10,
        lockedHint: "Guilds expect members who can hold their own in a fight.",
        label: "Guild",
        hint: "Hall, quests, treasury",
        icon: "M3 21V9l9-6 9 6v12M9 21v-6h6v6M3 21h18",
      },
      {
        id: "market",
        unlockLevel: 8,
        lockedHint: "Trading needs gold and gear you can spare — both come with a few levels.",
        label: "Market",
        hint: "Buy and sell",
        icon: "M4 8h16l-1 12H5L4 8Zm4 0V6a4 4 0 0 1 8 0v2",
      },
      {
        id: "arena",
        unlockLevel: 15,
        lockedHint: "Arena puts you against other players' geared characters.",
        label: "Arena",
        hint: "PvP matches",
        icon: "M14.5 3.5 20 9m0-5.5L14.5 9M6 21l6-6m-6 0 3 3m-6-9 9 9M4 4l7 7",
      },
    ],
  },
  {
    label: "Progression",
    tabs: [
      {
        id: "pass",
        unlockLevel: 5,
        lockedHint: "The season track needs a few levels of progress to show you anything.",
        label: "Battle Pass",
        hint: "Season rewards",
        icon: "M4 6h16v5a3 3 0 0 0 0 6v1H4v-1a3 3 0 0 0 0-6V6Zm6 0v12",
      },
      {
        id: "realm",
        label: "Realm",
        hint: "Friends, world, talents, records",
        icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-9-9h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18Z",
      },
    ],
  },
];

export const ALL_TABS: TabDef[] = [...PRIMARY_TABS, ...MORE_GROUPS.flatMap((g) => g.tabs)];

export function tabById(id: EmberTab): TabDef | undefined {
  return ALL_TABS.find((t) => t.id === id);
}

/** Classic components fire `game:setActiveTab` with these names. */
export function normalizeClassicTab(raw: string): EmberTab | null {
  const map: Record<string, EmberTab> = {
    Hero: "hero",
    Forge: "forge",
    Explore: "explore",
    Quests: "quests",
    Combat: "combat",
    Guild: "guild",
    Market: "market",
    Arena: "arena",
    Pass: "pass",
    "Battle Pass": "pass",
    "battle-pass": "pass",
    Realm: "realm",
    Progress: "realm",
    progress: "realm",
    realm: "realm",
  };
  return map[raw] ?? null;
}
