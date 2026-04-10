import { Page, expect } from '@playwright/test';

/**
 * Mock Discord SDK + OAuth for E2E testing
 * Allows tests to run without real Discord connection
 */

const MOCK_USER_ID = 'test_user_123';
const MOCK_GUILD_ID = 'test_guild_456';
const MOCK_ACCESS_TOKEN = 'test_access_token_789';

export async function setupMocks(page: Page) {
  // 1. FIRST: Mock all network routes before any navigation

  // Mock Discord user identity endpoint
  await page.route('https://discord.com/api/v10/users/@me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: MOCK_USER_ID,
        username: 'TestPlayer',
        discriminator: '0000',
        avatar: null,
      }),
    });
  });

  // Mock Discord OAuth token exchange
  await page.route('https://discord.com/api/oauth2/token', async (route) => {
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
  });

  // Mock local API token endpoint
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

  // 2. SECOND: Inject fake DiscordSDK BEFORE page loads
  await page.addInitScript(() => {
    // @ts-ignore
    window.DiscordSDK = {
      ready: async () => {
        return Promise.resolve({
          user: { id: 'test_user_123', username: 'TestPlayer' },
        });
      },
      commands: {
        authorize: async () => {
          return Promise.resolve({
            code: 'fake_auth_code',
            state: '',
          });
        },
      },
      guildId: 'test_guild_456',
      subscribe: () => {},
      unsubscribe: () => {},
    };

    // Also mock fetch if needed
    const originalFetch = window.fetch;
    // @ts-ignore
    window.fetch = async (url: string, options?: any) => {
      if (url.includes('/api/token')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ access_token: 'test_access_token_789' }),
        } as Response);
      }
      if (url.includes('discord.com/api/v10/users/@me')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 'test_user_123',
            username: 'TestPlayer',
          }),
        } as Response);
      }
      return originalFetch(url, options);
    };
  });
}

export const mockUserId = MOCK_USER_ID;
export const mockGuildId = MOCK_GUILD_ID;
export const mockAccessToken = MOCK_ACCESS_TOKEN;
