import { Bar } from 'react-chartjs-2'
import { baseOptions, chartColors } from './chartSetup'

export default function BarChart({ labels, datasets, euro = true, height = 240 }) {
  const data = {
    labels,
    datasets: datasets.map((ds) => ({
      backgroundColor: ds.color || chartColors.purple,
      borderRadius: 4,
      barPercentage: 0.6,
      categoryPercentage: 0.7,
      data: ds.data,
      label: ds.label,
    })),
  }

  return (
    <div style={{ height }}>
      <Bar data={data} options={baseOptions({ euro })} />
    </div>
  )
}