import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // jsdom : DOM simulé pour tester les méthodes qui touchent au DOM
    // (rendu, handlers). Les tests de logique pure n'en dépendent pas.
    environment: 'jsdom',
    include: ['tests_js/**/*.test.js'],
    // Pas de globals : on importe explicitement describe/it/expect.
    globals: false,
  },
});
