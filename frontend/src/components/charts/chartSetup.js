import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

// Enregistrement unique des modules Chart.js utilisés dans l'app
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

// Palette alignée sur le design system
export const chartColors = {
  purple: '#534AB7',
  purpleLight: '#EEEDFE',
  teal: '#1D9E75',
  red: '#E24B4A',
  amber: '#EF9F27',
  blue: '#378ADD',
  gray: '#B4B2A9',
  grid: 'rgba(0,0,0,0.04)',
  text: '#888780',
}

// Options communes : grille discrète, police cohérente, axes en euros
export function baseOptions({ euro = true } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1e1b4b',
        padding: 10,
        cornerRadius: 8,
        titleFont: { size: 12 },
        bodyFont: { size: 12 },
        callbacks: euro
          ? {
              label: (ctx) => {
                const v = ctx.parsed.y ?? ctx.parsed
                return ` ${Number(v).toLocaleString('fr-FR')} €`
              },
            }
          : {},
      },
    },
    scales: {
      x: {
        grid: { color: chartColors.grid },
        ticks: { font: { size: 11 }, color: chartColors.text },
      },
      y: {
        grid: { color: chartColors.grid },
        ticks: {
          font: { size: 11 },
          color: chartColors.text,
          callback: euro
            ? (v) => `${Number(v).toLocaleString('fr-FR')} €`
            : (v) => v,
        },
      },
    },
  }
}