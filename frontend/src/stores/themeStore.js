import { create } from 'zustand'

// Clé de persistance dans le navigateur
const STORAGE_KEY = 'budgetfamilial-theme'

// Modes possibles : 'system' (suit l'OS), 'light', 'dark'
function getStoredMode() {
  try {
    return localStorage.getItem(STORAGE_KEY) || 'system'
  } catch {
    return 'system'
  }
}

// Détermine si le mode sombre doit être actif selon le mode choisi
function resolveDark(mode) {
  if (mode === 'dark') return true
  if (mode === 'light') return false
  // mode 'system' : suit la préférence de l'OS
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

// Applique ou retire la classe .dark sur <html>
function applyTheme(isDark) {
  const root = document.documentElement
  if (isDark) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
}

export const useThemeStore = create((set, get) => ({
  mode: getStoredMode(),       // 'system' | 'light' | 'dark'
  isDark: resolveDark(getStoredMode()),

  setMode: (mode) => {
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // localStorage indisponible — on continue sans persistance
    }
    const isDark = resolveDark(mode)
    applyTheme(isDark)
    set({ mode, isDark })
  },

  // Initialise le thème au démarrage de l'app
  init: () => {
    const mode = get().mode
    const isDark = resolveDark(mode)
    applyTheme(isDark)
    set({ isDark })

    // Écoute les changements de préférence système (si mode 'system')
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      if (get().mode === 'system') {
        const newDark = resolveDark('system')
        applyTheme(newDark)
        set({ isDark: newDark })
      }
    }
    mql.addEventListener('change', handler)
  },
}))