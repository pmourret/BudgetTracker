import { Doughnut } from 'react-chartjs-2'
import { chartColors } from './chartSetup'

const DEFAULT_PALETTE = [
  chartColors.purple,
  chartColors.teal,
  chartColors.amber,
  chartColors.red,
  chartColors.blue,
  chartColors.gray,
]

export default function DoughnutChart({ labels, values, colors, height = 200 }) {
  const data = {
    labels,
    datasets: [
      {
        data: values,
        backgroundColor: colors || DEFAULT_PALETTE,
        borderWidth: 0,
        hoverOffset: 4,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '68%',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1e1b4b',
        padding: 10,
        cornerRadius: 8,
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed
            return ` ${Number(v).toLocaleString('fr-FR')} €`
          },
        },
      },
    },
  }

  return (
    <div style={{ height }}>
      <Doughnut data={data} options={options} />
    </div>
  )
}