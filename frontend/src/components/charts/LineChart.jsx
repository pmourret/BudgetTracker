import { Line } from 'react-chartjs-2'
import { baseOptions, chartColors } from './chartSetup'

export default function LineChart({ labels, datasets, euro = true, height = 240 }) {
  const data = {
    labels,
    datasets: datasets.map((ds) => ({
      borderColor: ds.color || chartColors.purple,
      backgroundColor: ds.fill ? `${ds.color || chartColors.purple}1a` : 'transparent',
      borderWidth: ds.width ?? 2,
      borderDash: ds.dashed ? [5, 4] : [],
      pointRadius: ds.points === false ? 0 : 3,
      pointBackgroundColor: ds.color || chartColors.purple,
      tension: 0.3,
      fill: ds.fill ?? false,
      data: ds.data,
      label: ds.label,
    })),
  }

  return (
    <div style={{ height }}>
      <Line data={data} options={baseOptions({ euro })} />
    </div>
  )
}