import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';

test.describe('Character Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Setup Discord mocks
    await setupMocks(page);
  });

  test('should create a character and enter the game', async ({ page }) => {
    // Log console messages for debugging
    page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err));

    // Navigate to the app
    await page.goto('/');

    // Wait for boot to complete AND for modal to appear
    // The app needs to: 1) load, 2) boot Discord SDK, 3) auth, 4) load inventory
    // If no character exists, show CreateCharacterModal
    await page.waitForLoadState('domcontentloaded');

    // Wait longer for the full auth+load cycle
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 30000 });

    // Verify modal is asking for character creation
    const modalText = page.locator('[role="dialog"]').first();
    await expect(modalText).toContainText(/Create|Character|Class/i);

    // Fill character name with unique timestamp
    const nameInput = page.locator('input[placeholder*="characters"]');
    const characterName = `TestHero_${Date.now()}`;
    await nameInput.fill(characterName);

    // Class may be selected automatically or not visible; try to click a class selector if present
    const classButtons = page.locator('[role="dialog"] button').filter({
      hasText: /warrior|mage|rogue|paladin/i,
    });

    if (await classButtons.count() > 0) {
      await classButtons.first().click();
    }
    // If no class buttons, the form defaults or doesn't require selection

    // Click "Begin adventure" or similar
    const submitBtn = page
      .locator('button')
      .filter({ hasText: /Begin|Start|Create/ });
    await expect(submitBtn.first()).toBeVisible();
    await submitBtn.first().click();

    // Modal should disappear
    await expect(modal).not.toBeVisible({ timeout: 10000 });

    // App should be in game (wait for tabs or shell to load)
    await page.waitForLoadState('networkidle');

    // Verify we see the game shell (tabs or main interface)
    const tabs = page.locator('button:has-text("Hero"), button:has-text("Explore"), button:has-text("Combat")');
    await expect(tabs.first()).toBeVisible({ timeout: 5000 });

    // Character name might appear in a header or profile section
    // (This is a soft assertion — the modal closing is the strong signal)
    const heroTab = page.locator('button:has-text("Hero")');
    await expect(heroTab).toBeVisible();
  });

  test('should reject invalid character names', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 30000 });

    // Try to submit with empty name
    const nameInput = page.locator('input[placeholder*="characters"]');
    await nameInput.fill(''); // Empty

    const submitBtn = page.locator('button').filter({ hasText: /Begin|Start|Create/ });

    // Submit button might be disabled or error appears
    // Just verify we don't enter the game with empty name
    const initialDisabled = await submitBtn.first().isDisabled();

    if (!initialDisabled) {
      // If enabled, click and expect error or modal to stay
      await submitBtn.first().click();
      await page.waitForTimeout(500);

      // Modal should still be visible (didn't leave)
      const stillVisible = await modal.isVisible();
      expect(stillVisible).toBe(true);
    }
  });
});
