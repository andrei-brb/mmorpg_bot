# Playwright E2E Test Suite

Critical path tests for the MMORPG Activity UI.

## Status

**Tests Created:** ✅ Full 5-scenario test suite  
**Tests Running:** ⚠️ Requires backend + auth setup

## Test Scenarios

| Spec | Tests | Purpose |
|------|-------|---------|
| 01_character_creation | 2 | Create character, validate names |
| 02_first_quest | 1 | Accept quest, kill 4 enemies, turn in |
| 03_combat | 3 | Start combat, flee, use potions |
| 04_dungeon | 2 | Browse catalog, solo enter |
| 05_item_enhancement | 3 | Open blacksmith, enhance items |

**Total: 11 tests covering core game loops**

---

## Running Tests

### Prerequisites

```bash
cd activity
npm install
npm install --save-dev @playwright/test
npx playwright install chromium
```

### Run Full Suite (Headless)
```bash
npm run test:e2e
```

### Run with UI (Interactive)
```bash
npm run test:e2e:ui
```

### Run Single Test File
```bash
npm run test:e2e -- 01_character_creation.spec.ts
```

---

## Current Issue: Discord Auth Mocking

**Problem:** Tests require Discord OAuth authentication, which our `addInitScript` mock can't fully intercept because the Discord SDK loads before our script runs.

**Current State:**
- ✅ Playwright infrastructure set up
- ✅ Test framework + configs ready
- ✅ All 5 test specs written with proper assertions
- ✅ Reusable helper library created
- ❌ Discord auth mocking incomplete

**Solutions:**

### Option A: Run Against Live Backend (Recommended for now)
1. Start the Python backend locally:
   ```bash
   python -m services.activity_http  # or however it's started
   ```
2. Create a Discord test application with OAuth credentials
3. Set `VITE_DISCORD_CLIENT_ID` in `.env.local`:
   ```
   VITE_DISCORD_CLIENT_ID=your_test_app_id
   ```
4. Get a Discord test account OAuth token and inject it:
   ```bash
   DISCORD_ACCESS_TOKEN=token npm run test:e2e
   ```
5. Tests will auth with real Discord, then hit local backend

### Option B: Mock at Build Time (Requires Vite Config Change)
Add a `test` environment in `vite.config.ts` that replaces the Discord SDK package:
```ts
define: {
  __MOCK_DISCORD__: true
}
```

Then in the app entry point, conditionally import a mock instead of the real SDK.

### Option C: Dedicated Test Server
Set up a test backend that returns fake Discord user data without validating OAuth.

---

## Test Architecture

### Files
```
e2e/
  ├── fixtures/
  │   ├── mockDiscord.ts       (65 lines) — Auth mocking
  │   └── gameHelpers.ts       (289 lines) — Reusable game actions
  └── tests/
      ├── 01_character_creation.spec.ts
      ├── 02_first_quest.spec.ts
      ├── 03_combat.spec.ts
      ├── 04_dungeon.spec.ts
      └── 05_item_enhancement.spec.ts
```

### Fixtures: `gameHelpers.ts`

Reusable test helpers:
- `createCharacter(page, name, classKey)` — Create a character
- `navigateToTab(page, tabName)` — Click tab
- `startCombat(page, enemyName)` — Start a fight
- `useAbility(page, abilityName)` — Use a skill
- `fightUntilOutcome(page, maxRounds)` — Fight until victory/defeat
- `acceptQuestOffer(page)` — Accept quest dialog
- `enterDungeon(page, dungeonName)` — Enter dungeon
- `enhanceItem(page, itemIndex)` — Open blacksmith + enhance

Each helper includes error handling and reasonable timeouts.

### Mocking Strategy: `mockDiscord.ts`

Currently mocks:
- ✅ Discord API endpoints (`/api/oauth2/token`, `/api/v10/users/@me`)
- ✅ Local token endpoint (`/api/token`)
- ✅ `window.DiscordSDK` object
- ❌ Real Discord SDK package initialization (too late in boot cycle)

---

## Next Steps

### Immediate
1. Choose Option A, B, or C above
2. Implement chosen solution
3. Re-run tests

### Short-term
- Add test hooks to CI/CD
- Screenshot artifacts on failure (already configured)
- Add test coverage reporting

### Long-term
- Expand to Option 1 (full 1-60 playthrough)
- Add performance benchmarks
- Add accessibility testing

---

## Debug Tips

### View Test in Browser
```bash
npm run test:e2e:ui
```
Opens interactive test explorer with video/trace replay.

### Screenshot on Failure
Already configured — check `test-results/` after failures.

### View Traces
```bash
npx playwright show-trace test-results/<test-name>/trace.zip
```

### Run Specific Test
```bash
npm run test:e2e -- 03_combat.spec.ts -g "should start combat"
```

---

## Test Data

Tests use unique character names with timestamps to avoid conflicts:
```ts
TestHero_${Date.now()}  // e.g., TestHero_1712769600000
```

No cleanup needed between runs — each test is isolated.

---

## Performance

Expected runtime:
- Character creation: ~5s
- Quest completion: ~3-5min (waiting for kills)
- Combat: ~5min
- Dungeon: ~3-5min
- Enhancement: ~2min

**Total: ~20 minutes** (sequential, single worker)

---

## Issues & Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "element(s) not found" for modal | Auth failed, app stuck at "Connecting..." | Implement Option A/B/C auth |
| Tests timeout | Backend not responding | Verify backend is running |
| Wrong selectors | UI changed | Update locators in helpers.ts |
| Tests pass locally, fail in CI | Env vars missing | Set VITE_DISCORD_CLIENT_ID in CI |

---

## Contributing

When adding new tests:
1. Add spec file to `e2e/tests/`
2. Import helpers from `./fixtures/gameHelpers.ts`
3. Follow naming: `describe()` → `test()`
4. Include `beforeEach` that calls `setupMocks(page)`
5. Use descriptive test names: "should X when Y"
6. Add timeout params: `{ timeout: 10000 }`

Example:
```ts
import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import { createCharacter, navigateToTab } from '../fixtures/gameHelpers';

test.describe('New Feature', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
  });

  test('should do something', async ({ page }) => {
    const char = `Test_${Date.now()}`;
    await createCharacter(page, char);
    await navigateToTab(page, 'Hero');
    // ... assertions
  });
});
```
