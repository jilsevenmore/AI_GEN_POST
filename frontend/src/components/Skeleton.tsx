import clsx from 'clsx'

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={clsx(
        'rounded-lg bg-gradient-to-r from-gray-100 via-gray-200 to-gray-100 bg-[length:200%_100%]',
        className
      )}
      style={{ animation: 'shimmer 1.6s linear infinite' }}
      aria-hidden="true"
    />
  )
}

/** Dashboard quick-action card skeleton */
export function QuickActionSkeleton() {
  return (
    <div className="card p-6 space-y-4">
      <Skeleton className="w-12 h-12 rounded-2xl" />
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  )
}

/** Table row skeleton */
export function TableRowSkeleton() {
  return (
    <tr>
      <td className="px-6 py-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-56" />
        </div>
      </td>
      <td className="px-6 py-4"><Skeleton className="h-5 w-12 rounded-full" /></td>
      <td className="px-6 py-4"><Skeleton className="h-5 w-24 rounded-full" /></td>
      <td className="px-6 py-4"><Skeleton className="h-2 w-28 rounded-full" /></td>
      <td className="px-6 py-4"><Skeleton className="h-4 w-20" /></td>
      <td className="px-6 py-4 text-right"><Skeleton className="h-8 w-16 rounded-xl ml-auto" /></td>
    </tr>
  )
}

/** Mobile job card skeleton */
export function JobCardSkeleton() {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-64" />
        </div>
        <Skeleton className="h-5 w-12 rounded-full" />
      </div>
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
      <Skeleton className="h-1.5 w-full rounded-full" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-8 w-16 rounded-xl" />
      </div>
    </div>
  )
}
