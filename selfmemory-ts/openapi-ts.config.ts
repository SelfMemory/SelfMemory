import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: '../docs/api/openapi.json',
  output: { path: 'src/generated', format: false, lint: false },
  plugins: ['@hey-api/client-fetch', '@hey-api/typescript', '@hey-api/sdk'],
})
