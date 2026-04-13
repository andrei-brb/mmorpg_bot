"use client"

import { useEffect, useState, useRef } from "react"

interface CooldownRingProps {
  totalSeconds: number
  onComplete: () => void
  size?: number
}

export function CooldownRing({ totalSeconds, onComplete, size = 52 }: CooldownRingProps) {
  const [remaining, setRemaining] = useState(totalSeconds)
  const calledRef = useRef(false)

  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const progress = remaining / totalSeconds
  const dashOffset = circumference * (1 - progress)

  useEffect(() => {
    calledRef.current = false
    setRemaining(totalSeconds)

    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval)
          if (!calledRef.current) {
            calledRef.current = true
            onComplete()
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [totalSeconds, onComplete])

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="-rotate-90"
        aria-hidden="true"
      >
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="oklch(0.28 0.025 75 / 0.4)"
          strokeWidth={4}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="oklch(0.74 0.13 80)"
          strokeWidth={4}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ transition: "stroke-dashoffset 0.9s linear" }}
        />
      </svg>
      <span className="absolute font-serif text-sm font-bold text-gold tabular-nums">
        {remaining}
      </span>
    </div>
  )
}
