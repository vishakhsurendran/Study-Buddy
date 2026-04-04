/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  // add other VITE_... vars here if needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
