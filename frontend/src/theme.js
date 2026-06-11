export const breakpoints = {
  mobile: 640,
}

export const spacing = {
  xs: '0.5rem',
  sm: '0.75rem',
  md: '1rem',
  lg: '1.25rem',
  xl: '1.5rem',
  '2xl': '2rem',
}

export const colors = {
  purple: '#534AB7',
  teal: '#1D9E75',
  red: '#E24B4A',
  amber: '#EF9F27',
  gray: '#B4B2A9',
  darkBg: '#1e1b4b',
  lightBg: '#f8fafc',
  white: '#ffffff',
  border: '#e2e8f0',
  text: {
    primary: '#1e293b',
    secondary: '#64748b',
    tertiary: '#94a3b8',
  }
}

export const typography = {
  fontFamily: {
    sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  fontSize: {
    xs: '12px',
    sm: '13px',
    base: '14px',
    lg: '16px',
    xl: '18px',
    '2xl': '20px',
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
  },
}

export const sizes = {
  buttonMobile: '44px',
  buttonDesktop: '40px',
  inputMobile: '44px',
  inputDesktop: '36px',
}

export const mediaQueries = {
  mobile: `(max-width: ${breakpoints.mobile - 1}px)`,
  desktop: `(min-width: ${breakpoints.mobile}px)`,
}

export const z = {
  base: 0,
  dropdown: 100,
  sticky: 500,
  fixed: 1000,
  modal: 2000,
  toast: 3000,
}
