'use client';

import React from 'react';

interface SilhouetteProps {
  type: 'goblin' | 'orc' | 'dragon' | 'knight' | 'wizard' | 'rogue' | 'merchant' | 'elder';
  color: string;
  className?: string;
}

export function EnemySilhouette({ type, color, className = '' }: SilhouetteProps) {
  const silhouettes: Record<string, JSX.Element> = {
    goblin: (
      <svg viewBox="0 0 100 120" className={className} fill={color}>
        <ellipse cx="50" cy="35" rx="18" ry="22" />
        <path d="M 32 35 Q 28 30 24 32" />
        <path d="M 68 35 Q 72 30 76 32" />
        <ellipse cx="50" cy="70" rx="22" ry="28" />
        <rect x="38" y="95" width="8" height="20" />
        <rect x="54" y="95" width="8" height="20" />
        <rect x="28" y="65" width="10" height="18" />
        <rect x="62" y="65" width="10" height="18" />
      </svg>
    ),
    orc: (
      <svg viewBox="0 0 100 130" className={className} fill={color}>
        <ellipse cx="50" cy="40" rx="20" ry="25" />
        <path d="M 30 40 Q 25 33 20 36" />
        <path d="M 70 40 Q 75 33 80 36" />
        <ellipse cx="50" cy="75" rx="26" ry="32" />
        <rect x="35" y="100" width="10" height="25" />
        <rect x="55" y="100" width="10" height="25" />
        <rect x="22" y="70" width="12" height="20" />
        <rect x="66" y="70" width="12" height="20" />
      </svg>
    ),
    dragon: (
      <svg viewBox="0 0 120 100" className={className} fill={color}>
        <ellipse cx="40" cy="50" rx="25" ry="30" />
        <path d="M 65 40 L 90 20 L 85 50 L 90 80 L 65 60 Z" />
        <circle cx="55" cy="35" r="8" />
        <path d="M 30 20 Q 20 15 15 20" />
        <path d="M 30 80 Q 20 85 15 80" />
        <ellipse cx="110" cy="50" rx="12" ry="18" />
      </svg>
    ),
    knight: (
      <svg viewBox="0 0 100 140" className={className} fill={color}>
        <path d="M 40 30 L 50 15 L 60 30 L 55 40 L 45 40 Z" />
        <rect x="38" y="38" width="24" height="35" />
        <path d="M 35 73 L 30 90 L 35 100 L 50 105 L 50 73 Z" />
        <path d="M 65 73 L 70 90 L 65 100 L 50 105 L 50 73 Z" />
        <rect x="42" y="100" width="6" height="30" />
        <rect x="52" y="100" width="6" height="30" />
        <circle cx="50" cy="55" r="6" fill="none" stroke={color} strokeWidth="2" />
      </svg>
    ),
    wizard: (
      <svg viewBox="0 0 90 130" className={className} fill={color}>
        <path d="M 30 10 L 45 5 L 60 10 L 50 25 L 40 25 Z" />
        <circle cx="45" cy="45" r="12" />
        <ellipse cx="45" cy="70" rx="18" ry="22" />
        <path d="M 30 90 L 25 130 L 30 125 L 35 130 Z" />
        <path d="M 60 90 L 65 130 L 60 125 L 55 130 Z" />
        <path d="M 35 50 Q 25 55 20 50" />
        <path d="M 55 50 Q 65 55 70 50" />
      </svg>
    ),
    rogue: (
      <svg viewBox="0 0 80 120" className={className} fill={color}>
        <circle cx="40" cy="30" r="12" />
        <path d="M 28 42 L 22 70 L 32 85 L 40 90 L 40 42 Z" />
        <path d="M 52 42 L 58 70 L 48 85 L 40 90 L 40 42 Z" />
        <path d="M 35 50 L 25 55" />
        <path d="M 45 50 L 55 55" />
      </svg>
    ),
    merchant: (
      <svg viewBox="0 0 100 130" className={className} fill={color}>
        <circle cx="50" cy="30" r="14" />
        <ellipse cx="50" cy="65" rx="20" ry="24" />
        <path d="M 35 85 L 32 125 L 38 120 L 42 130 Z" />
        <path d="M 65 85 L 68 125 L 62 120 L 58 130 Z" />
        <rect x="25" y="55" width="50" height="8" opacity="0.6" />
      </svg>
    ),
    elder: (
      <svg viewBox="0 0 100 130" className={className} fill={color}>
        <circle cx="50" cy="32" r="16" />
        <path d="M 40 25 L 35 18 M 60 25 L 65 18" />
        <ellipse cx="50" cy="70" rx="22" ry="26" />
        <path d="M 32 92 L 28 130 L 34 122 L 38 132 Z" />
        <path d="M 68 92 L 72 130 L 66 122 L 62 132 Z" />
        <path d="M 50 50 L 45 55" />
        <path d="M 50 50 L 55 55" />
      </svg>
    ),
  };

  return silhouettes[type] || silhouettes.goblin;
}

export function NPCSilhouette({ type, color, className = '' }: SilhouetteProps) {
  return <EnemySilhouette type={type} color={color} className={className} />;
}
