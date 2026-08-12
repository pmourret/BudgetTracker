import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// ESLint — frontend BudgetTracker.
//
// Jeu de règles volontairement court : ce qui est ici attrape des défauts qui
// se voient mal en relecture, pas des préférences de style. Aucune règle de
// mise en forme — elles ne trouvent rien et rendent la CI bavarde.
//
// Configuration alignée sur celle de FoyerOS. Ce n'est pas du partage de code
// entre dépôts (interdit, cf. suite §8) : chaque dépôt porte la sienne et peut
// en diverger, mais une divergence doit être délibérée.
//
// ⚠️ **Les règles « compilateur » de react-hooks v7 ne sont PAS activées**
// (`set-state-in-effect`, `refs`) : elles condamnent le motif « resynchroniser
// un état local sur la valeur du serveur par un effet », qui est un choix
// délibéré des deux fronts de la suite. À rouvrir si l'on adopte React
// Compiler — c'est un chantier, pas un réglage de CI.
export default [
    { ignores: ['dist/**', 'node_modules/**'] },

    js.configs.recommended,

    {
        files: ['**/*.{js,jsx}'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: globals.browser,
            parserOptions: {
                ecmaFeatures: { jsx: true },
            },
        },
        plugins: {
            react,
            'react-hooks': reactHooks,
            'react-refresh': reactRefresh,
        },
        rules: {
            // ⚠️ Indispensable : sans elle, `no-unused-vars` ne voit pas qu'un
            // composant reçu en prop est utilisé en `<Icon />` et signale des
            // faux positifs en série.
            'react/jsx-uses-vars': 'error',

            'react-hooks/rules-of-hooks': 'error',
            'react-hooks/exhaustive-deps': 'error',

            'no-unused-vars': [
                'error',
                { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^_' },
            ],

            'react-refresh/only-export-components': [
                'warn',
                { allowConstantExport: true },
            ],
        },
    },
]
