import { Page } from '@playwright/test';

/**
 * Mock Discord + Game API endpoints for E2E testing
 * The Discord SDK itself is mocked at the module level (mockDiscordSDK.ts)
 * This fixture mocks /api/token endpoint and essential game API routes
 */

const MOCK_ACCESS_TOKEN = 'test_token_' + Date.now();
const MOCK_GUILD_ID = 'test_guild_456';

export async function setupMocks(page: Page) {
  // Track combat state for this test page
  let combatTurns = 0;
  let enemyHp = 20; // Enemy dies in 2 hits (20 damage per action)
  // Mock the /api/token endpoint — exchanges fake auth code for test token
  await page.route('**/api/token', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: MOCK_ACCESS_TOKEN,
        ok: true,
      }),
    });
  });

  // Mock game API endpoints — essential for character creation flow
  await page.route('**/api/game/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // GET /api/game/inventory
    if (url.includes('/api/game/inventory')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          discord: { id: 'test_user_123', username: 'TestPlayer' },
          character: null, // No character yet — will trigger CreateCharacterModal
          items: [],
          gold: 0,
        }),
      });
    }
    // POST /api/game/character/create
    else if (url.includes('/api/game/character/create') && method === 'POST') {
      const body = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          character: {
            id: 'char_' + Date.now(),
            name: body.name || 'TestHero',
            class: body.class_key || 'warrior',
            level: 1,
            health: 100,
            max_health: 100,
            gold: 0,
            experience: 0,
          },
        }),
      });
    }
    // GET /api/game/progress
    else if (url.includes('/api/game/progress')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          character: {
            level: 1,
            health: 100,
            max_health: 100,
            gold: 0,
            class: 'warrior',
            specialization: null,
          },
        }),
      });
    }
    // GET /api/game/map
    else if (url.includes('/api/game/map')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          current_zone: 'elwynn_forest',
          zones: [
            { key: 'elwynn_forest', name: 'Elwynn Forest', level_min: 1, level_max: 10 },
          ],
        }),
      });
    }
    // GET /api/game/quests
    else if (url.includes('/api/game/quests')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          quests: [],
          active_quest: null,
        }),
      });
    }
    // GET /api/game/combat/snapshot
    else if (url.includes('/api/game/combat/snapshot')) {
      if (enemyHp <= 0) {
        // Combat ended with victory
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            active: false,
            enemies: [],
            ended_outcome: {
              outcome: {
                title: 'Victory!',
                lines: ['You defeated the Defias Bandit!', 'Gained 50 XP and 25 gold.'],
              },
            },
          }),
        });
      } else {
        // Combat still active
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            active: true,
            enemies: [],
            state: {
              turn: combatTurns,
              player: {
                name: 'Player',
                current_hp: 95,
                max_hp: 100,
                current_res: 75,
                max_res: 100,
                res_type: 'Rage',
                class: 'warrior',
              },
              enemy: { name: 'Defias Bandit', current_hp: enemyHp, max_hp: 30 },
              log: [],
              abilities: [
                { key: 'sword_slash', name: 'Sword Slash', emoji: '⚔️', cost: 0, cost_type: 'Rage', cooldown: 0 },
                { key: 'shield_bash', name: 'Shield Bash', emoji: '🛡️', cost: 25, cost_type: 'Rage', cooldown: 0 },
              ],
              can_potion: true,
            },
          }),
        });
      }
    }
    // GET /api/game/deeds
    else if (url.includes('/api/game/deeds')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          flags: [],
        }),
      });
    }
    // GET /api/game/live-events
    else if (url.includes('/api/game/live-events')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          events: [],
        }),
      });
    }
    // GET /api/game/character/class-options
    else if (url.includes('/api/game/character/class-options')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          classes: [
            { key: 'warrior', name: 'Warrior', emoji: '⚔️', role: 'Tank', resource: 'Rage' },
            { key: 'mage', name: 'Mage', emoji: '🔥', role: 'DPS', resource: 'Mana' },
            { key: 'rogue', name: 'Rogue', emoji: '🗡️', role: 'DPS', resource: 'Energy' },
          ],
        }),
      });
    }
    // GET /api/game/character/stats
    else if (url.includes('/api/game/character/stats')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          attack_power: 10,
          spell_power: 8,
          dmg_min: 5,
          dmg_max: 15,
          armor: 20,
          crit_chance: 5.5,
          dodge_chance: 3.2,
          haste: 1.0,
          lifesteal: 0,
          resistance: 0,
          hit_rating: 0,
          class_mastery: { class_key: 'warrior', level: 1, xp: 0 },
          top_ability_mastery: [],
        }),
      });
    }
    // POST /api/game/explore
    else if (url.includes('/api/game/explore') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          encounter_type: 'enemy',
          enemy_key: 'defias_bandit',
          name: 'Defias Bandit',
        }),
      });
    }
    // POST /api/game/npc/interact
    else if (url.includes('/api/game/npc/interact') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          interaction_type: 'quest_offer',
          quest_id: 'test_quest_1',
        }),
      });
    }
    // POST /api/game/quest/offer/accept
    else if (url.includes('/api/game/quest/offer/accept') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      });
    }
    // GET /api/game/combat/enemies
    else if (url.includes('/api/game/combat/enemies')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          enemies: [
            { key: 'defias_bandit', name: 'Defias Bandit', level: 1 },
            { key: 'forest_spider', name: 'Forest Spider', level: 2 },
          ],
        }),
      });
    }
    // POST /api/game/combat/start
    else if (url.includes('/api/game/combat/start') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          state: {
            turn: 1,
            player: {
              name: 'Player',
              current_hp: 100,
              max_hp: 100,
              current_res: 100,
              max_res: 100,
              res_type: 'Rage',
              class: 'warrior',
            },
            enemy: { name: 'Defias Bandit', current_hp: 20, max_hp: 20 },
            log: ['Combat started!'],
            abilities: [
              { key: 'sword_slash', name: 'Sword Slash', emoji: '⚔️', cost: 0, cost_type: 'Rage', cooldown: 0 },
              { key: 'shield_bash', name: 'Shield Bash', emoji: '🛡️', cost: 25, cost_type: 'Rage', cooldown: 1 },
            ],
            can_potion: true,
          },
        }),
      });
    }
    // POST /api/game/combat/action
    else if (url.includes('/api/game/combat/action') && method === 'POST') {
      combatTurns++;
      enemyHp = Math.max(0, enemyHp - 20); // Damage enemy by 20 each turn (dies in 1 hit)

      if (enemyHp <= 0) {
        // Return outcome after defeating enemy
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            outcome: {
              title: 'Victory!',
              lines: ['You defeated the Defias Bandit!', 'Gained 50 XP and 25 gold.'],
            },
          }),
        });
      } else {
        // Continue fighting
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            state: {
              turn: combatTurns + 1,
              player: {
                name: 'Player',
                current_hp: 95,
                max_hp: 100,
                current_res: 75,
                max_res: 100,
                res_type: 'Rage',
                class: 'warrior',
              },
              enemy: { name: 'Defias Bandit', current_hp: enemyHp, max_hp: 30 },
              log: ['Combat started!', 'You used Sword Slash for 10 damage!'],
              abilities: [
                { key: 'sword_slash', name: 'Sword Slash', emoji: '⚔️', cost: 0, cost_type: 'Rage', cooldown: 0 },
                { key: 'shield_bash', name: 'Shield Bash', emoji: '🛡️', cost: 25, cost_type: 'Rage', cooldown: 0 },
              ],
              can_potion: true,
            },
          }),
        });
      }
    }
    // POST /api/game/combat/flee
    else if (url.includes('/api/game/combat/flee') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          outcome: {
            title: 'Fled from Combat',
            lines: ['You successfully escaped from the Defias Bandit!'],
          },
        }),
      });
    }
    // GET /api/game/dungeons
    else if (url.includes('/api/game/dungeons')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          dungeons: [
            { key: 'blackfathom_deeps', name: 'Blackfathom Deeps', level_min: 10, level_max: 20, floor: 1 },
          ],
        }),
      });
    }
    // POST /api/game/dungeon/enter
    else if (url.includes('/api/game/dungeon/enter') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          active: true,
          floor: 1,
          enemy: { key: 'test_enemy', name: 'Test Enemy', hp: 50, max_hp: 50 },
        }),
      });
    }
    // GET /api/game/item/**/enhance-info
    else if (url.match(/\/api\/game\/item\/[^/]+\/enhance-info/)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          item_id: 'test_item',
          current_level: 0,
          max_level: 10,
          cost_gold: 100,
          success_rate: 0.8,
        }),
      });
    }
    // POST /api/game/item/**/enhance
    else if (url.match(/\/api\/game\/item\/[^/]+\/enhance/) && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          success: true,
          new_level: 1,
        }),
      });
    }
    // GET /api/game/specializations
    else if (url.includes('/api/game/specializations')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          needs_choice: false,
          options: [],
          spec_unlock_level: 10,
        }),
      });
    }
    // For any other /api/game/* routes, return a generic success
    else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      });
    }
  });

  // Mock Discord API endpoints (rarely hit since Discord SDK is mocked)
  await page.route('https://discord.com/api/**', async (route) => {
    const url = route.request().url();

    if (url.includes('/users/@me')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test_user_123',
          username: 'TestPlayer',
          discriminator: '0000',
          avatar: null,
        }),
      });
    } else if (url.includes('/oauth2/token')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: MOCK_ACCESS_TOKEN,
          token_type: 'Bearer',
          expires_in: 604800,
          refresh_token: 'fake_refresh_token',
          scope: 'identify applications.commands',
        }),
      });
    } else {
      await route.abort();
    }
  });
}

export const mockAccessToken = MOCK_ACCESS_TOKEN;
export const mockGuildId = MOCK_GUILD_ID;
