import { Doughnut } from 'react-chartjs-2'

/**
 * ⚠️ **Aucune palette par défaut empruntée aux couleurs d'état.**
 *
 * Elle valait `purple, teal, amber, red, blue, gray` — c'est-à-dire exactement
 * la sémantique monétaire de l'application : le turquoise « entrant » servait à
 * désigner un type d'actif, le rouge « sortant » un autre.
 * (D05 de la revue UI/UX du 2026-08-20.)
 *
 * `colors` est désormais **obligatoire** : l'appelant connaît ses entités, donc
 * lui seul peut leur donner une couleur stable (`usePaletteDonnees`). Un défaut
 * silencieux redeviendrait une palette de rang.
 */

export default function DoughnutChart({ labels, values, colors, height = 200 }) {
  const data = {
    labels,
    datasets: [
      {
        data: values,
        backgroundColor: colors,
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