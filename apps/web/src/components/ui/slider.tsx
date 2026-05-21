import * as React from 'react'
import { cn } from '../../lib/utils'

type SliderProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange'> & {
  value: number
  onValueChange: (value: number) => void
}

export function Slider({ className, value, onValueChange, min = 0, max = 100, step = 1, ...props }: SliderProps) {
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(event) => onValueChange(Number(event.target.value))}
      className={cn('h-2 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50', className)}
      {...props}
    />
  )
}
