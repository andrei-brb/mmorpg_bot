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

Enable: open the activity with ?mock=1 (persists in localStorage), or set
localStorage key discord_activity_mock_preview to "1".

Disable: ?mock=0 clears the flag and turns mock mode off.

See style.css block "Full-tab mock preview".
