import type { ReactNode } from 'react'
import { motion, MotionConfig, useReducedMotion } from 'motion/react'

export function PixMotionLoader({ label }: { label: ReactNode }) {
  const reduceMotion = useReducedMotion()
  const spinDuration = reduceMotion ? 2.2 : 1.05
  const pulseScale = reduceMotion ? [1, 1.03, 1] : [0.96, 1.1, 0.96]

  return (
    <MotionConfig reducedMotion="never">
      <div className="pix-motion-loader-stage flex flex-col items-center gap-3 p-6 text-center text-muted-foreground" aria-live="polite" aria-busy="true">
        <div className="pix-motion-loader" aria-hidden="true">
          <motion.div
            className="pix-motion-loader-ring pix-motion-loader-ring-main"
            animate={{ rotate: 360 }}
            transition={{ duration: spinDuration, repeat: Infinity, ease: 'linear' }}
          />
          <motion.div
            className="pix-motion-loader-core"
            animate={{ opacity: [0.72, 1, 0.72], scale: pulseScale }}
            transition={{ duration: reduceMotion ? 1.6 : 1.05, repeat: Infinity, ease: 'easeInOut' }}
          />
        </div>
        <p className="pix-motion-loader-label text-sm font-bold">
          {label}
          <LoaderDots reduceMotion={reduceMotion} />
        </p>
      </div>
    </MotionConfig>
  )
}

function LoaderDots({ reduceMotion }: { reduceMotion: boolean | null }) {
  return (
    <span className="inline-flex min-w-5 justify-start" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          animate={{ opacity: [0.28, 1, 0.28] }}
          transition={{ duration: reduceMotion ? 1.2 : 0.78, repeat: Infinity, delay: index * 0.16, ease: 'easeInOut' }}
        >
          .
        </motion.span>
      ))}
    </span>
  )
}
