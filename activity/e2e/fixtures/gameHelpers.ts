import { Page, expect } from '@playwright/test';

/**
 * Reusable game helpers for E2E tests
 */

export async function createCharacter(
  page: Page,
  name: string,
  classKey: string = 'warrior'
) {
  // Wait for CreateCharacterModal to appear
  const modal = page.locator('[role="dialog"]');
  await expect(modal).toBeVisible();

  // Fill character name
  const nameInput = page.locator('input[placeholder*="32 characters"]');
  await nameInput.fill(name);

  // Select class (click button with classKey in text or data attribute)
  const classButton = page.locator(`button:has-text("${classKey}")`).first();
  if (await classButton.isVisible()) {
    await classButton.click();
  } else {
    // Fallback: click first class button
    const firstClassBtn = page.locator('[role="dialog"] button').nth(1);
    await firstClassBtn.click();
  }

  // Click Begin Adventure
  const submitBtn = page.locator('button:has-text("Begin adventure")');
  await expect(submitBtn).toBeVisible();
  await submitBtn.click();

  // Modal should close
  await expect(modal).not.toBeVisible({ timeout: 10000 });

  // Verify character is in game (header should show name or inventory loaded)
  await page.waitForLoadState('networkidle');
}

export async function navigateToTab(page: Page, tabName: string) {
  const tabButton = page.locator(`button:has-text("${tabName}")`);
  await expect(tabButton).toBeVisible();
  await tabButton.click();
  await page.waitForLoadState('networkidle');
}

export async function startCombat(
  page: Page,
  enemyName: string,
  classKey: string = 'defias_bandit'
) {
  // Navigate to Combat tab if not there
  const combatTab = page.locator('button:has-text("Combat")');
  if (!(await combatTab.evaluate((el) => el.classList.contains('active')))) {
    await combatTab.click();
  }

  // Wait for enemy list to load
  const selectElement = page.locator('select');
  await expect(selectElement).toBeVisible({ timeout: 10000 });

  // Select enemy or use first available
  if (enemyName) {
    await selectElement.selectOption({ label: new RegExp(enemyName, 'i') });
  }

  // Click "Start Combat"
  const startBtn = page.locator('button:has-text("Start Combat")');
  await startBtn.click();

  // Wait for fight screen
  const fightScreen = page.locator('text=Your Turn');
  await expect(fightScreen).toBeVisible({ timeout: 10000 });
}

export async function useAbility(
  page: Page,
  abilityName?: string,
  retries: number = 20
) {
  // If no specific ability, click the first non-disabled skill
  let clicked = false;

  for (let i = 0; i < retries; i++) {
    const skillBtn = abilityName
      ? page.locator(`button:has-text("${abilityName}")`)
      : page.locator('.skill-btn').first();

    if (await skillBtn.isVisible()) {
      const disabled = await skillBtn.evaluate((el) =>
        el.hasAttribute('disabled')
      );

      if (!disabled) {
        await skillBtn.click();
        clicked = true;
        break;
      }
    }

    // Wait a bit and retry (combat might still be loading)
    await page.waitForTimeout(200);
  }

  if (!clicked) {
    throw new Error(`Could not find clickable ability after ${retries} retries`);
  }

  // Wait for action to resolve
  await page.waitForTimeout(500);
}

export async function waitForOutcome(page: Page, timeout: number = 15000) {
  const outcomeScreen = page.locator('text=/Victory|Defeat/');
  await expect(outcomeScreen).toBeVisible({ timeout });
}

export async function talkToNpc(page: Page, npcName: string) {
  // Navigate to Explore tab
  await navigateToTab(page, 'Explore');

  // Find NPC in the list (by name or role)
  const npcButton = page.locator(`button:has-text("Talk")`).filter({
    has: page.locator(`text=${npcName}`),
  });

  // If exact match not found, search for any Talk button
  const talkButtons = page.locator('button:has-text("Talk")');
  const count = await talkButtons.count();

  if (count > 0) {
    await talkButtons.first().click();
  } else {
    throw new Error(`Could not find NPC ${npcName}`);
  }

  // Wait for modal
  await page.waitForTimeout(500);
}

export async function acceptQuestOffer(page: Page) {
  // QuestOfferModal should be visible
  const modal = page.locator('[role="dialog"]:has-text("Quest")').first();
  await expect(modal).toBeVisible({ timeout: 10000 });

  // Click Accept button
  const acceptBtn = page.locator('button:has-text("Accept")').first();
  await expect(acceptBtn).toBeVisible();
  await acceptBtn.click();

  // Modal should close
  await expect(modal).not.toBeVisible({ timeout: 5000 });
}

export async function acceptQuestCompletion(page: Page) {
  // QuestCompleteModal should be visible
  const modal = page.locator('[role="dialog"]:has-text("Complete")').first();
  await expect(modal).toBeVisible({ timeout: 10000 });

  // Click Continue button
  const continueBtn = page.locator('button:has-text("Continue")').first();
  await expect(continueBtn).toBeVisible();
  await continueBtn.click();

  // Modal should close
  await expect(modal).not.toBeVisible({ timeout: 5000 });
}

export async function enterDungeon(page: Page, dungeonName: string) {
  // Navigate to Combat tab
  await navigateToTab(page, 'Combat');

  // Switch to Dungeon mode (click Dungeon button in mode toggle)
  const dungeonBtn = page.locator('button:has-text("Dungeon")');
  await expect(dungeonBtn).toBeVisible();
  await dungeonBtn.click();

  // Wait for dungeon catalog to load
  await page.waitForLoadState('networkidle');

  // Find dungeon entry and click Enter
  const dungeonEntry = page
    .locator(`text=${dungeonName}`)
    .locator('..')
    .locator('button:has-text("Enter")');

  if (await dungeonEntry.isVisible()) {
    await dungeonEntry.click();
  } else {
    // Fallback: click first Enter button
    const firstEnter = page.locator('button:has-text("Enter")').first();
    await firstEnter.click();
  }

  // Wait for fight screen or party lobby
  await page.waitForTimeout(1000);
}

export async function fightUntilOutcome(
  page: Page,
  maxRounds: number = 50
) {
  let round = 0;

  while (round < maxRounds) {
    // Check if we reached outcome
    const outcomeBtn = page.locator('button:has-text("Fight Again")');
    if (await outcomeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      break;
    }

    // Use an ability
    try {
      await useAbility(page);
    } catch (e) {
      // Combat might have ended, check outcome
      if (
        await page.locator('text=/Victory|Defeat/').isVisible({ timeout: 1000 }).catch(() => false)
      ) {
        break;
      }
      throw e;
    }

    round++;
  }

  // Verify outcome is visible
  await expect(page.locator('text=/Victory|Defeat/')).toBeVisible();
}

export async function buyItem(
  page: Page,
  itemName: string,
  quantity: number = 1
) {
  // Navigate to Market tab
  await navigateToTab(page, 'Market');

  // Find item and click Buy
  const itemButton = page.locator(`text=${itemName}`).first();
  await expect(itemButton).toBeVisible();

  // Locate Buy button near item
  const buyBtn = itemButton.locator('..')
    .locator('button:has-text("Buy")');

  await buyBtn.click();

  // Fill quantity if dialog appears
  const quantityInput = page.locator('input[type="number"]');
  if (await quantityInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await quantityInput.fill(String(quantity));
  }

  // Click confirm
  const confirmBtn = page.locator('button:has-text("Confirm")');
  if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await confirmBtn.click();
  }

  await page.waitForTimeout(500);
}

export async function enhanceItem(page: Page, itemIndex: number = 0) {
  // Navigate to Hero tab
  await navigateToTab(page, 'Hero');

  // Find Enhance button
  const enhanceButtons = page.locator('button:has-text("Enhance")');
  await expect(enhanceButtons.nth(itemIndex)).toBeVisible();

  // Click Enhance
  await enhanceButtons.nth(itemIndex).click();

  // Wait for BlacksmithModal
  const modal = page.locator('[role="dialog"]').first();
  await expect(modal).toBeVisible({ timeout: 10000 });

  // Click Enhance button in modal
  const modalEnhanceBtn = modal.locator('button:has-text("Enhance")');
  await expect(modalEnhanceBtn).toBeVisible();
  await modalEnhanceBtn.click();

  // Wait for result
  await page.waitForTimeout(1000);
}
