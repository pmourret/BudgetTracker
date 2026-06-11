import { useEffect } from 'react'

export default function Modal({ isOpen, onClose, title, children, footer }) {
  useEffect(() => {
    if (!isOpen) return
    const handleEsc = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEsc)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.body.style.overflow = ''
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 bg-slate-900/60 flex justify-center items-stretch sm:items-center p-0 sm:p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-surface flex flex-col overflow-hidden w-full h-full rounded-none sm:w-[480px] sm:max-w-full sm:h-auto sm:max-h-[90vh] sm:rounded-xl"
      >
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-app shrink-0">
          <span className="text-base font-medium text-content">{title}</span>
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="text-content-2 text-xl leading-none p-1 cursor-pointer hover:text-content"
          >
            ✕
          </button>
        </div>
        <div className="p-5 overflow-y-auto flex-1">{children}</div>
        {footer && (
          <div className="flex gap-3 justify-end px-5 py-4 border-t border-border-app shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}