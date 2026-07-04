import FluxSearchPanel from '../components/flux/FluxSearchPanel'

export default function FluxPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-medium text-content">Flux</h1>
        <p className="text-sm text-content-2 mt-0.5">
          Recherchez et filtrez tous les mouvements du foyer.
        </p>
      </div>

      <FluxSearchPanel enableCreate />
    </div>
  )
}
