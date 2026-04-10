/**
 * Mock Discord Embedded App SDK for E2E testing
 * Provides fake implementations of all required methods without actual Discord auth
 */

const MOCK_USER_ID = 'test_user_123';
const MOCK_USERNAME = 'TestPlayer';
const MOCK_GUILD_ID = 'test_guild_456';
const MOCK_CHANNEL_ID = 'test_channel_789';

export class DiscordSDK {
  clientId: string;
  guildId: string = MOCK_GUILD_ID;
  channelId: string = MOCK_CHANNEL_ID;

  private subscriptions: Map<string, Set<(...args: any[]) => void>> = new Map();

  constructor(clientId: string) {
    this.clientId = clientId;
  }

  async ready(): Promise<{ user: { id: string; username: string } }> {
    // Simulate Discord SDK boot completing
    return Promise.resolve({
      user: {
        id: MOCK_USER_ID,
        username: MOCK_USERNAME,
      },
    });
  }

  commands = {
    authorize: async (options?: {
      client_id?: string;
      response_type?: string;
      state?: string;
      prompt?: string;
      scope?: string[];
    }) => {
      // Simulate OAuth flow — return fake auth code
      return Promise.resolve({
        code: 'fake_auth_code_' + Date.now(),
        state: options?.state || '',
      });
    },

    authenticate: async (options?: { access_token?: string }) => {
      // No-op in test mode
      return Promise.resolve({});
    },
  };

  subscribe(event: string, callback: (...args: any[]) => void): void {
    if (!this.subscriptions.has(event)) {
      this.subscriptions.set(event, new Set());
    }
    this.subscriptions.get(event)?.add(callback);
  }

  unsubscribe(event: string, callback: (...args: any[]) => void): void {
    this.subscriptions.get(event)?.delete(callback);
  }
}

export default DiscordSDK;
