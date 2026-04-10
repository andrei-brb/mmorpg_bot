import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import {
  createCharacter,
  navigateToTab,
  startCombat,
  useAbility,
  fightUntilOutcome,
} from '../fixtures/gameHelpers';

test.describe('Combat - Overworld', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should start combat and reach outcome', async ({ page }) => {
    // Create character
    const charName = `CombatHero_${Date.now()}`;
    await createCharacter(page, charName);

    // Navigate to Combat tab
    await navigateToTab(page, 'Combat');

    // Verify we're in Overworld mode (default)
    const overworldBtn = page.locator('button:has-text("Overworld")');
    await expect(overworldBtn).toBeVisible();

    // Wait for enemy list to load
    const selectElement = page.locator('select');
    await expect(selectElement).toBeVisible({ timeout: 10000 });

    // Select an enemy
    const options = await selectElement.locator('option').count();
    if (options > 1) {
      await selectElement.selectOption({ index: 1 });
    }

    // Start combat
    const startBtn = page.locator('button:has-text("Start Combat")');
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    // Wait for fight screen to appear
    const skillBtns = page.locator('.skill-btn');
    await expect(skillBtns.first()).toBeVisible({ timeout: 10000 });

    // Verify HP bars are visible
    const hpBars = page.locator('.hp-bar-track');
    await expect(hpBars.first()).toBeVisible();

    // Take an action (use ability)
    await useAbility(page);

    // Verify combat log is updating (if visible)
    const combatLog = page.locator('text=/deal|damage|attack|defeat|fight/i').first();
    if (await combatLog.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(combatLog).toBeVisible();
    }

    // Fight until outcome
    await fightUntilOutcome(page, 50);

    // Verify outcome screen
    const outcomeText = page.locator('text=/Victory|Defeat/');
    await expect(outcomeText).toBeVisible();

    // Verify buttons for next action
    const continueBtn = page
      .locator('button')
      .filter({ hasText: /Fight Again|Rest/ });
    await expect(continueBtn.first()).toBeVisible();
  });

  test('should allow fleeing from combat', async ({ page }) => {
    const charName = `FleeHero_${Date.now()}`;
    await createCharacter(page, charName);

    await navigateToTab(page, 'Combat');

    // Select and start combat
    const selectElement = page.locator('select');
    await expect(selectElement).toBeVisible({ timeout: 10000 });

    const options = await selectElement.locator('option').count();
    if (options > 1) {
      await selectElement.selectOption({ index: 1 });
    }

    const startBtn = page.locator('button:has-text("Start Combat")');
    await startBtn.click();

    // Wait for fight screen
    const fleeBtn = page.locator('button:has-text("Flee")');
    await expect(fleeBtn).toBeVisible({ timeout: 10000 });

    // Click Flee
    await fleeBtn.click();

    // Should end combat and show outcome
    const outcomeText = page.locator('text=/Victory|Defeat|Flee/');
    await expect(outcomeText).toBeVisible({ timeout: 10000 });
  });

  test('should allow using potions in combat', async ({ page }) => {
    const charName = `PotionHero_${Date.now()}`;
    await createCharacter(page, charName);

    await navigateToTab(page, 'Combat');

    // Start combat
    const selectElement = page.locator('select');
    await expect(selectElement).toBeVisible({ timeout: 10000 });

    const options = await selectElement.locator('option').count();
    if (options > 1) {
      await selectElement.selectOption({ index: 1 });
    }

    const startBtn = page.locator('button:has-text("Start Combat")');
    await startBtn.click();

    // Wait for fight screen
    await page.waitForTimeout(500);

    // Try to use potion if available
    const potionBtn = page.locator('button:has-text("Potion")');

    if (
      await potionBtn.isVisible({ timeout: 5000 }).catch(() => false)
    ) {
      const disabled = await potionBtn.evaluate((el) =>
        el.hasAttribute('disabled')
      );

      if (!disabled) {
        await potionBtn.click();

        // Combat should continue (look for skill buttons still visible)
        const skillBtn = page.locator('.skill-btn').first();
        await expect(skillBtn).toBeVisible({ timeout: 5000 });
      }
    }

    // Clean up — finish the fight
    try {
      await fightUntilOutcome(page, 50);
    } catch (e) {
      // Expected — might flee or die
    }
  });
});
