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

const bridgeablePlugin = {
  rules: {
    'widget-handlers-edit-mode-gated': widgetHandlersEditModeGated,
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
    },
  },
])
