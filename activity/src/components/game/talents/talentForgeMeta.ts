import {
  Crosshair,
  Crown,
  Flame,
  Hammer,
  Heart,
  Shield,
  Skull,
  Sparkles,
  Star,
  Sword,
  Zap,
  type LucideIcon,
} from "lucide-react";

export const SPEC_UNLOCK_LEVEL = 10;

export const CLASS_LABELS: Record<string, string> = {
  warrior: "Warrior",
  paladin: "Paladin",
  mage: "Mage",
  rogue: "Rogue",
  priest: "Priest",
  hunter: "Hunter",
};

export const SPEC_META: Record<string, { name: string; tagline: string; icon: LucideIcon }> = {
  arms: { name: "Arms", tagline: "Two-handed devastation. Bleed and execute.", icon: Sword },
  protection: { name: "Protection", tagline: "Shield wall. Guardian of the line.", icon: Shield },
  retribution: { name: "Retribution", tagline: "Holy wrath. Vengeance in every strike.", icon: Sword },
  holy_paladin: { name: "Holy", tagline: "Beacon of the Light. Heal and protect.", icon: Heart },
  fire: { name: "Fire", tagline: "Living flame. Burn everything.", icon: Flame },
  frost: { name: "Frost", tagline: "Ice and control. Shatter your foes.", icon: Skull },
  assassination: { name: "Assassination", tagline: "Poison and precision. Silent death.", icon: Skull },
  subtlety: { name: "Subtlety", tagline: "Shadow and burst. Strike unseen.", icon: Zap },
  holy_priest: { name: "Holy", tagline: "Divine healing and shields.", icon: Heart },
  shadow: { name: "Shadow", tagline: "Void power. Damage over time.", icon: Skull },
  marksmanship: { name: "Marksmanship", tagline: "Deadly precision at range.", icon: Crosshair },
  beast_mastery: { name: "Beast Mastery", tagline: "Master of beasts. Fight as one.", icon: Sparkles },
};

export const CLASS_FOUNDATION_FLAVOR: Record<string, string> = {
  warrior: "Forge the warrior within. Preview both paths before level 10.",
  paladin: "Swear your oath. Channel Light before your calling.",
  mage: "Study the arcane foundations before your school.",
  rogue: "Hone your tools. Choose shadow or poison.",
  priest: "Devotion first — shadow or Light awaits.",
  hunter: "Track, aim, tame — choose your wilderness path.",
};
