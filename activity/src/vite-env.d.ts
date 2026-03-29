/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DISCORD_CLIENT_ID: string;
  /** Empty = same origin (Activity proxy). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
