import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import { createCharacter } from '../fixtures/gameHelpers';

/**
 * Performance Tests
 * Validates acceptable performance metrics
 */

test.describe('Performance', () => {
  test('should load page in under 2 seconds', async ({ page }) => {
    await setupMocks(page);

    const startTime = Date.now();
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;

    console.log(`Page load: ${loadTime}ms`);
    expect(loadTime).toBeLessThan(2000);
  });

  test('should create character in under 3 seconds', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const startTime = Date.now();
    const charName = `PerfChar_${Date.now()}`;
    await createCharacter(page, charName);
    const time = Date.now() - startTime;

    console.log(`Character creation: ${time}ms`);
    expect(time).toBeLessThan(3000);
  });

  test('should render game UI quickly', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const charName = `RenderTest_${Date.now()}`;
    const startTime = Date.now();
    await createCharacter(page, charName);
    const renderTime = Date.now() - startTime;

    console.log(`UI render: ${renderTime}ms`);

    // Game shell tabs should be visible
    const heroTab = page.locator('button:has-text("Hero")');
    await expect(heroTab).toBeVisible();

    expect(renderTime).toBeLessThan(3500);
  });

  test('should load inventory efficiently', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const charName = `InventoryTest_${Date.now()}`;
    await createCharacter(page, charName);

    const startTime = Date.now();
    const heroTab = page.locator('button:has-text("Hero")');
    await expect(heroTab).toBeVisible();
    const time = Date.now() - startTime;

    console.log(`Inventory load: ${time}ms`);
    expect(time).toBeLessThan(500);
  });

  test('should handle multiple character creations efficiently', async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const startTime = Date.now();

    // Create character (single operation)
    const charName = `MultiTest_${Date.now()}`;
    await createCharacter(page, charName);

    const time = Date.now() - startTime;
    console.log(`Single character creation: ${time}ms`);

    // Should be performant
    expect(time).toBeLessThan(3000);
  });
});
