import { Bar } from 'react-chartjs-2'
import { baseOptions, chartColors } from './chartSetup'

export default function BarChart({
  labels,
  datasets,
  euro = true,
  height = 240,
  stacked = false,
}) {
  const data = {
    labels,
    datasets: datasets.map((ds) => ({
      backgroundColor: ds.color || chartColors.purple,
      borderRadius: 4,
      barPercentage: stacked ? 0.8 : 0.6,
      categoryPercentage: stacked ? 0.8 : 0.7,
      data: ds.data,
      label: ds.label,
    })),
  }

  const options = baseOptions({ euro })
  if (stacked) {
    options.scales.x.stacked = true
    options.scales.y.stacked = true
  }
  // Plusieurs séries → légende utile (masquée par défaut dans baseOptions).
  if (datasets.length > 1) {
    options.plugins.legend = {
      display: true,
      position: 'bottom',
      labels: { boxWidth: 10, boxHeight: 10, font: { size: 11 }, color: chartColors.text },
    }
  }

  return (
    <div style={{ height }}>
      <Bar data={data} options={options} />
    </div>
  )
}