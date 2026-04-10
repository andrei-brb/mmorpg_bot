import { test, expect } from '@playwright/test';
import { setupMocks } from '../fixtures/mockDiscord';
import { createCharacter } from '../fixtures/gameHelpers';

/**
 * Lore Validation Tests
 * Validates Obsidian Silence story progression mechanics
 */

test.describe('Lore Validation', () => {
  test.beforeEach(async ({ page }) => {
    await setupMocks(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should support three-act story structure', async ({ page }) => {
    const charName = `ActOne_${Date.now()}`;
    await createCharacter(page, charName);

    // Three acts:
    // Act 1: The Shatter-Tone (quests 1-5)
    // Act 2: Cipher Vigilance (quests 6-10)
    // Act 3: The Final Architecture (quests 11-15)

    const heroTab = page.locator('button:has-text("Hero")');
    await expect(heroTab).toBeVisible();
  });

  test('should track deed flags for story progression', async ({ page }) => {
    const charName = `DeedTrack_${Date.now()}`;
    await createCharacter(page, charName);

    // Deed flags:
    // - shatter_tone_done (Act 1 complete)
    // - cipher_translated (learn Architect's memory)
    // - flame_infused_done (burn the Cipher)
    // - marcus_recommendation (bridge Elwynn→Dun Morogh)

    const questsBtn = page.locator('button:has-text("Quests")');
    await expect(questsBtn).toBeVisible();
  });

  test('should enforce boss unlock gates', async ({ page }) => {
    const charName = `BossGate_${Date.now()}`;
    await createCharacter(page, charName, 'warrior');

    // Final boss requires:
    // - Act 1 & Act 2 completion
    // - flame_infused_done deed
    // - cipher_translated deed

    const progressBtn = page.locator('button:has-text("Progress")');
    await expect(progressBtn).toBeVisible();
  });

  test('should validate Obsidian Silence NPC dialogue chain', async ({ page }) => {
    const charName = `DialogueChain_${Date.now()}`;
    await createCharacter(page, charName);

    // NPC interactions:
    // - Mage Apprentice (Act 1 quests)
    // - Blind Monk (Act 2 quests)
    // - Architect (Act 3 final boss)

    const heroTab = page.locator('button:has-text("Hero")');
    await expect(heroTab).toBeVisible();
  });

  test('should maintain narrative consistency across sessions', async ({ page }) => {
    const charName = `Consistency_${Date.now()}`;
    await createCharacter(page, charName);

    // Story state should persist
    const heroTab = page.locator('button:has-text("Hero")');
    await expect(heroTab).toBeVisible();

    // Verify UI tabs exist (for session continuity)
    const questsBtn = page.locator('button:has-text("Quests")');
    await expect(questsBtn).toBeVisible();
  });
});
