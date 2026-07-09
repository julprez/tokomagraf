import { type ReactNode } from 'react'
import { type LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

const SIZE_CLASSES = {
  sm: 'py-8',
  md: 'py-12',
  lg: 'py-16',
}

const ICON_SIZES = {
  sm: 'w-8 h-8',
  md: 'w-12 h-12',
  lg: 'w-16 h-16',
}

export function EmptyState({ icon: Icon, title, description, action, size = 'md' }: EmptyStateProps) {
  return (
    <div className={`card text-center ${SIZE_CLASSES[size]}`}>
      <div className="mx-auto mb-4 p-4 rounded-full bg-surface-light/50 inline-flex">
        <Icon className={`${ICON_SIZES[size]} text-gray-600`} />
      </div>
      <h2 className="text-lg font-semibold text-gray-300 mb-1">{title}</h2>
      {description && (
        <p className="text-sm text-gray-500 max-w-md mx-auto mb-4">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
