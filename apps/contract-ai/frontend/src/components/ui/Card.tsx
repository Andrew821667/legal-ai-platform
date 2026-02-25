import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  hover?: boolean
  gradient?: boolean
  className?: string
  onClick?: () => void
}

export default function Card({
  children,
  hover = false,
  gradient = false,
  className = '',
  onClick
}: CardProps) {
  const baseStyles = 'bg-white rounded-2xl shadow-card p-6 border border-gray-100'
  const hoverStyles = hover ? 'hover:shadow-card-hover cursor-pointer' : ''
  const gradientStyles = gradient ? 'bg-gradient-to-br from-white to-gray-50' : ''

  return (
    <motion.div
      whileHover={hover ? { y: -4 } : {}}
      onClick={onClick}
      className={`
        ${baseStyles}
        ${hoverStyles}
        ${gradientStyles}
        ${className}
        transition-all duration-300
      `}
    >
      {children}
    </motion.div>
  )
}
