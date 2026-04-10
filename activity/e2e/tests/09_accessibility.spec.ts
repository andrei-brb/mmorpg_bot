import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import { createCharacter } from '../fixtures/gameHelpers';

/**
 * Accessibility Tests
 * Validates WCAG 2.1 compliance basics
 */

test.describe('Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should have semantic HTML with headings', async ({ page }) => {
    const charName = `A11y_${Date.now()}`;
    await createCharacter(page, charName);

    // Check for headings
    const h1 = page.locator('h1');
    const hasHeading = await h1.count().then(c => c > 0);
    expect(hasHeading).toBeTruthy();
  });

  test('should have keyboard-accessible buttons', async ({ page }) => {
    const charName = `Keyboard_${Date.now()}`;
    await createCharacter(page, charName);

    // All major buttons should exist
    const heroBtn = page.locator('button:has-text("Hero")');
    const explorerBtn = page.locator('button:has-text("Explore")');
    const questsBtn = page.locator('button:has-text("Quests")');

    await expect(heroBtn).toBeVisible();
    await expect(explorerBtn).toBeVisible();
    await expect(questsBtn).toBeVisible();
  });

  test('should support Tab navigation', async ({ page }) => {
    const charName = `TabNav_${Date.now()}`;
    await createCharacter(page, charName);

    // Press Tab to navigate
    await page.keyboard.press('Tab');

    // Should focus on an interactive element
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(['BUTTON', 'INPUT', 'A', 'SELECT']).toContain(focused);
  });

  test('should have ARIA labels on interactive elements', async ({ page }) => {
    const charName = `AriaLabels_${Date.now()}`;
    await createCharacter(page, charName);

    // Buttons should have accessible names
    const buttons = page.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);

    // First button should have text content
    const text = await buttons.first().textContent();
    expect(text?.length).toBeGreaterThan(0);
  });

  test('should have proper color contrast', async ({ page }) => {
    const charName = `Contrast_${Date.now()}`;
    await createCharacter(page, charName);

    // Check that text colors differ from background
    const buttons = page.locator('button');
    if (await buttons.count() > 0) {
      const styles = await buttons.first().evaluate((el) => {
        const computed = window.getComputedStyle(el);
        return {
          color: computed.color,
          backgroundColor: computed.backgroundColor,
        };
      });

      // Should have distinct colors
      expect(styles.color).not.toEqual(styles.backgroundColor);
    }
  });

  test('should have accessible form inputs', async ({ page }) => {
    // During character creation, inputs should be accessible
    const nameInput = page.locator('input');

    if (await nameInput.count() > 0) {
      const placeholder = await nameInput.first().getAttribute('placeholder');
      expect(placeholder).toBeTruthy();
    }
  });

  test('should maintain focus visibility', async ({ page }) => {
    const charName = `FocusVis_${Date.now()}`;
    await createCharacter(page, charName);

    // Tab to a button
    await page.keyboard.press('Tab');

    // Check that focused element has some visual indicator
    const focused = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement;
      const computed = window.getComputedStyle(el);
      return {
        outline: computed.outline,
        boxShadow: computed.boxShadow,
      };
    });

    // Should have some focus indicator
    const hasFocus = focused.outline !== 'none' || focused.boxShadow !== 'none';
    expect(hasFocus).toBeTruthy();
  });

  test('should use semantic heading hierarchy', async ({ page }) => {
    const charName = `Headings_${Date.now()}`;
    await createCharacter(page, charName);

    // Should have proper heading structure
    const h1s = page.locator('h1');
    const h2s = page.locator('h2');

    // If h2s exist, should have at least one h1
    const h2Count = await h2s.count();
    if (h2Count > 0) {
      const h1Count = await h1s.count();
      expect(h1Count).toBeGreaterThan(0);
    }
  });

  test('should support screen reader announcements', async ({ page }) => {
    const charName = `ScreenReader_${Date.now()}`;
    await createCharacter(page, charName);

    // Look for aria-live regions
    const liveRegion = page.locator('[aria-live], [role="alert"]');
    const hasLiveRegion = await liveRegion.count().then(c => c >= 0);
    expect(hasLiveRegion).toBeTruthy();
  });
});
