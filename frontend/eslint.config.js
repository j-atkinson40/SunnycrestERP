import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

// Phase R-1.5 — local plugin hosting the widget-handlers-edit-mode-gated rule.
// Heuristic: any file under `src/components/widgets/` that declares a
// `handle*` / `on*` function but does not mention `_editMode` in its
// source is flagged. See `eslint-rules/widget-handlers-edit-mode-gated.js`.
import widgetHandlersEditModeGated from './eslint-rules/widget-handlers-edit-mode-gated.js'
// R-2.0 — entity card import discipline. Ensures DeliveryCard /
// AncillaryCard / OrderCard are imported from the visual-editor
// registrations barrel (which re-exports the wrapped versions
// carrying data-component-name) rather than directly from their
// source files (which would yield the unwrapped *Raw component and
// break runtime-editor click-to-edit).
import entityCardWrappedImport from './eslint-rules/entity-card-wrapped-import.js'

const bridgeablePlugin = {
  rules: {
    'widget-handlers-edit-mode-gated': widgetHandlersEditModeGated,
    'entity-card-wrapped-import': entityCardWrappedImport,
  },
}

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      bridgeable: bridgeablePlugin,
    },
    rules: {
      // R-1.5: widget operational handlers must mention `_editMode`
      // for runtime editor safety. Warning during development; CI
      // gate promotes to error before merge.
      'bridgeable/widget-handlers-edit-mode-gated': 'warn',
      // R-2.0: error on direct imports of raw entity-card components
      // — production code must use the wrapped versions from the
      // registrations barrel.
      'bridgeable/entity-card-wrapped-import': 'error',
    },
  },
])
