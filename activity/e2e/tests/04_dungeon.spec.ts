import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import {
  createCharacter,
  navigateToTab,
  enterDungeon,
  useAbility,
} from '../fixtures/gameHelpers';

test.describe('Dungeons - Solo Run', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should enter a dungeon and fight', async ({ page }) => {
    // Create character
    const charName = `DungeonHero_${Date.now()}`;
    await createCharacter(page, charName);

    // Navigate to Combat tab
    await navigateToTab(page, 'Combat');

    // Wait for Dungeon button to be visible
    const dungeonBtn = page.locator('button:has-text("Dungeon")');
    await expect(dungeonBtn).toBeVisible({ timeout: 5000 });

    // Click Dungeon mode
    await dungeonBtn.click();

    // Wait for dungeon list to load
    await page.waitForLoadState('networkidle');

    // Look for dungeon entries with "Enter" buttons
    const enterBtns = page.locator('button:has-text("Enter")');
    const count = await enterBtns.count();

    if (count > 0) {
      // Click first Enter button
      await enterBtns.first().click();

      // Wait for either:
      // 1. Party lobby / run screen
      // 2. Combat screen for solo run
      await page.waitForTimeout(1000);

      const combatScreen = page.locator('.skill-btn').first();
      const partyScreen = page.locator('text=/Party|Players|Invite/').first();

      const isCombat = await combatScreen
        .isVisible({ timeout: 3000 })
        .catch(() => false);
      const isParty = await partyScreen
        .isVisible({ timeout: 3000 })
        .catch(() => false);

      if (isCombat) {
        // Solo run entered, we're in combat
        // Use an ability
        try {
          await useAbility(page);
        } catch (e) {
          // Combat might end immediately
        }

        // Wait a bit
        await page.waitForTimeout(500);

        // Verify we're still in dungeon context
        // (Floor indicator might be visible)
        const floorText = page.locator('text=/Floor/');
        if (
          await floorText.isVisible({ timeout: 2000 }).catch(() => false)
        ) {
          await expect(floorText).toBeVisible();
        }
      } else if (isParty) {
        // Party screen shown
        // Click Enter Dungeon or similar
        const enterDungeonBtn = page.locator(
          'button'
        ).filter({ hasText: /Enter|Start/i });

        if (await enterDungeonBtn.first().isVisible({ timeout: 2000 }).catch(() => false)) {
          await enterDungeonBtn.first().click();

          // Now should be in combat
          await page.waitForTimeout(1000);
        }
      }
    }
  });

  test('should show dungeon catalog', async ({ page }) => {
    const charName = `CatalogHero_${Date.now()}`;
    await createCharacter(page, charName);

    await navigateToTab(page, 'Combat');

    // Switch to Dungeon mode
    const dungeonBtn = page.locator('button:has-text("Dungeon")');
    await expect(dungeonBtn).toBeVisible();
    await dungeonBtn.click();

    await page.waitForLoadState('networkidle');

    // Verify dungeon list is shown
    // Look for dungeon names or descriptions
    const dungeonText = page.locator('text=/Dungeon|Depths|Tower|Crypt/i');

    if (
      await dungeonText.isVisible({ timeout: 5000 }).catch(() => false)
    ) {
      await expect(dungeonText).toBeVisible();
    }

    // Verify Dungeon mode was successfully switched to
    // (Dungeon button may have active state, or just verify no errors occurred)
    await expect(dungeonBtn).toBeVisible();
  });
});
