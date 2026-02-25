import { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'default'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function Badge({
  children,
  variant = 'default',
  size = 'md',
  className = ''
}: BadgeProps) {
  const variants = {
    success: 'bg-gradient-to-r from-success-400 to-success-600 text-white',
    warning: 'bg-gradient-to-r from-warning-400 to-warning-600 text-white',
    danger: 'bg-gradient-to-r from-danger-400 to-danger-600 text-white',
    info: 'bg-gradient-to-r from-primary-400 to-primary-600 text-white',
    default: 'bg-gray-100 text-gray-700'
  }

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base'
  }

  return (
    <span className={`
      inline-flex items-center font-semibold rounded-full shadow-sm
      ${variants[variant]}
      ${sizes[size]}
      ${className}
    `}>
      {children}
    </span>
  )
}
