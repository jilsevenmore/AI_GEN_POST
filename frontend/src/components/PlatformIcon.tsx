import React from 'react'
import { Instagram, Facebook, Linkedin, Twitter, Globe, Send } from 'lucide-react'

export type SupportedPlatform = 'instagram' | 'facebook' | 'linkedin' | 'twitter' | string

interface PlatformIconProps {
  platform: SupportedPlatform
  className?: string
  size?: number
}

export function PlatformIcon({ platform, className = 'h-5 w-5', size }: PlatformIconProps) {
  const norm = (platform || '').toLowerCase().trim()

  switch (norm) {
    case 'instagram':
      return <Instagram className={className} size={size} />
    case 'facebook':
      return <Facebook className={className} size={size} />
    case 'linkedin':
      return <Linkedin className={className} size={size} />
    case 'twitter':
    case 'x':
      return <Twitter className={className} size={size} />
    case 'buffer':
      return <Send className={className} size={size} />
    default:
      return <Globe className={className} size={size} />
  }
}

export const platformColors: Record<string, string> = {
  instagram: 'bg-gradient-to-tr from-amber-500 via-rose-500 to-purple-600 text-white',
  facebook: 'bg-[#1877F2] text-white',
  linkedin: 'bg-[#0A66C2] text-white',
  twitter: 'bg-black text-white',
  buffer: 'bg-[#231F20] text-white',
}

export const platformBadgeColors: Record<string, string> = {
  instagram: 'bg-pink-50 text-pink-700 border-pink-200',
  facebook: 'bg-blue-50 text-blue-700 border-blue-200',
  linkedin: 'bg-sky-50 text-sky-700 border-sky-200',
  twitter: 'bg-gray-100 text-gray-800 border-gray-200',
}
