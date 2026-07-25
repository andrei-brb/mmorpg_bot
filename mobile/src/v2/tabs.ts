/**
 * The information architecture, and the single biggest change in this redesign.
 *
 * The classic UI has 10 top-level tabs, and they are organised by SYSTEM — each
 * backend feature got a tab. It's worse than 10, actually: Realm alone hides 7
 * sub-tabs, Market has 4 modes, Guild has 9 stacked panels. Something like 30
 * distinct screens behind a slide-out drawer.
 *
 * That's a map of how the game was BUILT, not how it's PLAYED. A player never
 * thinks "I want the Realm system." They think one of five things:
 *
 *   Camp     what's waiting for me?          (return ritual, claimables)
 *   Venture  I want to go do something       (explore, fight, dungeons, quests)
 *   Hero     I want to get stronger          (gear, inventory, forge, talents)
 *   Realm    I want to deal with people      (guild, market, arena, friends)
 *   Legend   how am I doing, long term?      (pass, prestige, records, story)
 *
 * Five intents, five tabs. Nothing is removed — everything from the 30 screens
 * lives under one of these, and the grouping is what makes 30 screens findable.
 */

export type EmberTab = "camp" | "venture" | "hero" | "realm" | "legend";

export type TabDef = {
  id: EmberTab;
  label: string;
  /** Inline SVG path data (24x24). Icons are drawn, not emoji, so they take the
   *  active/inactive colour and stay crisp. */
  icon: string;
  question: string;
};

export const EMBER_TABS: TabDef[] = [
  {
    id: "camp",
    label: "Camp",
    question: "What's waiting for me?",
    // a flame
    icon: "M12 2c.5 3.5-1.5 4.5-3 6.5C7.4 10.6 6 12.4 6 15a6 6 0 0 0 12 0c0-2.2-1-3.6-2-5-.6 1-1.2 1.6-2 2 .5-3.5-1-6.5-2-10Z",
  },
  {
    id: "venture",
    label: "Venture",
    question: "I want to go do something",
    // a folded map
    icon: "M9 4 3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4Zm0 0v13m6-10.5v13",
  },
  {
    id: "hero",
    label: "Hero",
    question: "I want to get stronger",
    // a shield
    icon: "M12 3 5 6v5.5c0 4.3 2.9 8.3 7 9.5 4.1-1.2 7-5.2 7-9.5V6l-7-3Z",
  },
  {
    id: "realm",
    label: "Realm",
    question: "I want to deal with people",
    // two figures
    icon: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7 1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM3 19c0-3 2.7-5 6-5s6 2 6 5m1-5c2.8 0 5 1.7 5 4",
  },
  {
    id: "legend",
    label: "Legend",
    question: "How am I doing?",
    // a star
    icon: "m12 3 2.6 5.7 6.4.7-4.7 4.2 1.3 6.4L12 16.8 6.4 20l1.3-6.4L3 9.4l6.4-.7L12 3Z",
  },
];
