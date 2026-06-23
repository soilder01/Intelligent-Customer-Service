import js from '@eslint/js';
import tseslint from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  { ignores: ['dist'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { parser: tsParser, parserOptions: { ecmaVersion: 'latest', sourceType: 'module' }, globals: { document: 'readonly', fetch: 'readonly', console: 'readonly', import: 'readonly', HTMLInputElement: 'readonly', HTMLDivElement: 'readonly', React: 'readonly' } },
    plugins: { '@typescript-eslint': tseslint, 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: { ...tseslint.configs.recommended.rules, ...reactHooks.configs.recommended.rules, 'react-refresh/only-export-components': 'warn' },
  },
];
