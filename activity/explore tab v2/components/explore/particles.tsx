'use client';

import React, { useEffect, useState } from 'react';

interface Particle {
  id: string;
  x: number;
  y: number;
  tx: number;
  ty: number;
  color: string;
  size: number;
  delay: number;
}

interface ParticleEffectProps {
  type: 'enemy' | 'boss' | 'treasure' | 'npc' | 'safe';
  centerX: number;
  centerY: number;
  count?: number;
}

const getParticleConfig = (type: string) => {
  const configs: Record<string, { color: string; burst: number }> = {
    enemy: { color: 'oklch(0.52 0.22 25)', burst: 0.6 }, // red
    boss: { color: 'oklch(0.52 0.18 300)', burst: 0.8 }, // purple
    treasure: { color: 'oklch(0.74 0.13 80)', burst: 0.7 }, // gold
    npc: { color: 'oklch(0.58 0.12 195)', burst: 0.5 }, // teal
    safe: { color: 'oklch(0.55 0.14 150)', burst: 0.4 }, // green
  };
  return configs[type] || configs.safe;
};

export function ParticleEffect({
  type,
  centerX,
  centerY,
  count = 12,
}: ParticleEffectProps) {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    const config = getParticleConfig(type);
    const newParticles: Particle[] = Array.from({ length: count }).map(
      (_, i) => {
        const angle = (i / count) * Math.PI * 2;
        const distance = 60 + Math.random() * 40;
        const tx = Math.cos(angle) * distance;
        const ty = Math.sin(angle) * distance;

        return {
          id: `${type}-${Date.now()}-${i}`,
          x: centerX,
          y: centerY,
          tx,
          ty,
          color: config.color,
          size: 4 + Math.random() * 6,
          delay: i * 30,
        };
      }
    );
    setParticles(newParticles);
  }, [type, centerX, centerY, count]);

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden">
      {particles.map((p) => (
        <div
          key={p.id}
          className="absolute animate-particle"
          style={{
            left: p.x,
            top: p.y,
            '--tx': `${p.tx}px`,
            '--ty': `${p.ty}px`,
            '--delay': `${p.delay}ms`,
            animationDelay: `${p.delay}ms`,
          } as React.CSSProperties & { '--tx': string; '--ty': string; '--delay': string }}
        >
          <div
            className="rounded-full"
            style={{
              width: p.size,
              height: p.size,
              backgroundColor: p.color,
              boxShadow: `0 0 ${p.size}px ${p.color}`,
            }}
          />
        </div>
      ))}
    </div>
  );
}

export function SilhouetteGlow({ color }: { color: string }) {
  return (
    <div
      className="absolute inset-0 rounded-full blur-3xl opacity-40 animate-glow"
      style={{ backgroundColor: color }}
    />
  );
}
