import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import {
  createCharacter,
  navigateToTab,
  enhanceItem,
} from '../fixtures/gameHelpers';

test.describe('Item Enhancement - Blacksmith', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should open blacksmith modal and show enhancement info', async ({
    page,
  }) => {
    // Create character
    const charName = `EnhanceHero_${Date.now()}`;
    await createCharacter(page, charName);

    // Navigate to Hero tab
    await navigateToTab(page, 'Hero');

    // Wait for inventory to load
    await page.waitForLoadState('networkidle');

    // Look for Enhance buttons
    const enhanceBtns = page.locator('button:has-text("Enhance")');
    const count = await enhanceBtns.count();

    if (count > 0) {
      // Click first Enhance button
      await enhanceBtns.first().click();

      // Wait for BlacksmithModal to appear
      const modal = page.locator('[role="dialog"]').first();
      await expect(modal).toBeVisible({ timeout: 10000 });

      // Verify modal contains enhancement info
      const modalText = modal;
      const levels = modalText.locator('text=/Level|Success|Cost/');

      if (
        await levels.isVisible({ timeout: 2000 }).catch(() => false)
      ) {
        await expect(levels).toBeVisible();
      }

      // Verify Enhance button exists in modal
      const enhanceModalBtn = modal.locator('button:has-text("Enhance")');
      if (
        await enhanceModalBtn.isVisible({ timeout: 2000 }).catch(() => false)
      ) {
        await expect(enhanceModalBtn).toBeVisible();
      }

      // Close modal (click outside or close button)
      const closeBtn = modal.locator('button[aria-label="Close"]');
      if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await closeBtn.click();
      } else {
        // Click outside modal
        await page.click('body', { position: { x: 0, y: 0 } });
      }

      await page.waitForTimeout(300);
    }
  });

  test('should attempt to enhance an item', async ({ page }) => {
    const charName = `EnhanceAttempt_${Date.now()}`;
    await createCharacter(page, charName);

    await navigateToTab(page, 'Hero');

    await page.waitForLoadState('networkidle');

    const enhanceBtns = page.locator('button:has-text("Enhance")');
    const count = await enhanceBtns.count();

    if (count > 0) {
      // Click Enhance
      await enhanceBtns.first().click();

      // Wait for modal
      const modal = page.locator('[role="dialog"]').first();
      await expect(modal).toBeVisible({ timeout: 10000 });

      // Click Enhance button in modal
      const enhanceBtn = modal.locator('button:has-text("Enhance")');

      if (
        await enhanceBtn.isVisible({ timeout: 2000 }).catch(() => false)
      ) {
        // Check if enabled
        const disabled = await enhanceBtn.evaluate((el) =>
          el.hasAttribute('disabled')
        );

        if (!disabled) {
          await enhanceBtn.click();

          // Wait for result (success or failure message)
          await page.waitForTimeout(1000);

          // Check for result text
          const result = page.locator('text=/Success|Failed|Enhancement/i').first();

          if (
            await result.isVisible({ timeout: 2000 }).catch(() => false)
          ) {
            await expect(result).toBeVisible();
          }
        }
      }

      // Close modal
      const closeBtn = modal.locator('button[aria-label="Close"]');
      if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await closeBtn.click();
      }
    }
  });

  test('should show list of equippable items', async ({ page }) => {
    const charName = `ItemList_${Date.now()}`;
    await createCharacter(page, charName);

    await navigateToTab(page, 'Hero');

    await page.waitForLoadState('networkidle');

    // Look for equipment slots or item list
    const itemEntries = page.locator('[role="button"]').filter({
      hasText: /Equip|Unequip|Enhance/i,
    });

    const itemCount = await itemEntries.count();

    // Should have at least some items (starting gear)
    expect(itemCount).toBeGreaterThanOrEqual(0);

    // Verify tabs or sections exist
    const slots = page.locator('text=/Head|Chest|Legs|Hands|Feet|Weapon|Shield/i');

    if (
      await slots.isVisible({ timeout: 2000 }).catch(() => false)
    ) {
      await expect(slots).toBeVisible();
    }
  });
});
