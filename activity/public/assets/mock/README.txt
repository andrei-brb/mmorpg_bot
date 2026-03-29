Full-tab mock preview (visual check only)
==========================================

Place art here so ?mock=1 can show them (extensions must match):

  hero.png
  explore.jpeg
  quests.jpeg
  progress.jpeg
  before-combat.jpeg  — Combat tab: enemy selection screen.
  combat.jpeg         — Combat tab: in-combat (turn-based) screen.

On the Combat tab in mock mode, use the floating “Enemy select” / “In combat”
control (bottom-right) to switch between those two PNGs. Your choice is saved
in localStorage (discord_activity_mock_combat_view).

Enable mock mode (any one works; all persist in localStorage until you turn off):

  • Browser: add ?mock=1 to the URL
  • Discord Activity often strips query strings — use the hash instead:
    your-activity-url#mock=1
  • In Discord (or anywhere): triple-click the title "World of Discord" in the
    header to toggle mock mode on/off (page reloads).

Disable: ?mock=0 or #mock=0, or triple-click the title again.

If Discord shows "could not connect" but mock mode is on, you still get tab bar +
full-tab mock images (disconnected layout uses the same tab pane IDs).

See style.css block "Full-tab mock preview".
