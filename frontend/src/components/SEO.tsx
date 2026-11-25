import { useEffect } from 'react'

type JsonLd = Record<string, unknown> | Array<Record<string, unknown>>

type SEOProps = {
  title: string
  description?: string
  path?: string
  type?: 'website' | 'article'
  image?: string
  robots?: string
  jsonLd?: JsonLd
  keywords?: string[]
}

const SITE_NAME = 'EVENMORE INFOTECH'
const DEFAULT_SITE_URL = (import.meta as any).env?.VITE_SITE_URL || 'https://evenmoreinfotech.com'
const DEFAULT_IMAGE = (import.meta as any).env?.VITE_OG_IMAGE_URL || `${DEFAULT_SITE_URL.replace(/\/$/, '')}/og-default.svg`

function setMeta(selector: string, attr: 'content' | 'href', value: string, createTag: () => HTMLElement) {
  let el = document.head.querySelector(selector) as HTMLElement | null
  if (!el) {
    el = createTag()
    document.head.appendChild(el)
  }
  el.setAttribute(attr, value)
}

function setMetaByName(name: string, content: string) {
  setMeta(`meta[name="${name}"]`, 'content', content, () => {
    const m = document.createElement('meta')
    m.setAttribute('name', name)
    return m
  })
}

function setMetaByProperty(property: string, content: string) {
  setMeta(`meta[property="${property}"]`, 'content', content, () => {
    const m = document.createElement('meta')
    m.setAttribute('property', property)
    return m
  })
}

function setLink(rel: string, href: string) {
  setMeta(`link[rel="${rel}"]`, 'href', href, () => {
    const l = document.createElement('link')
    l.setAttribute('rel', rel)
    return l
  })
}

export function SEO({
  title,
  description = 'EVENMORE INFOTECH — ERP, CRM, HRMS, Inventory, PMS & Custom Software for Indian businesses.',
  path,
  type = 'website',
  image = DEFAULT_IMAGE,
  robots = 'index,follow',
  jsonLd,
  keywords,
}: SEOProps) {
  useEffect(() => {
    const fullTitle = title.includes(SITE_NAME) ? title : `${title} | ${SITE_NAME}`
    const base = DEFAULT_SITE_URL.replace(/\/$/, '')
    const url = path ? `${base}${path.startsWith('/') ? path : `/${path}`}` : window.location.origin + window.location.pathname

    document.title = fullTitle
    setMetaByName('description', description)
    setMetaByName('robots', robots)
    if (keywords?.length) setMetaByName('keywords', keywords.join(', '))

    setMetaByProperty('og:title', fullTitle)
    setMetaByProperty('og:description', description)
    setMetaByProperty('og:type', type)
    setMetaByProperty('og:url', url)
    setMetaByProperty('og:site_name', SITE_NAME)
    setMetaByProperty('og:image', image)

    setMetaByName('twitter:card', 'summary_large_image')
    setMetaByName('twitter:title', fullTitle)
    setMetaByName('twitter:description', description)
    setMetaByName('twitter:image', image)

    setLink('canonical', url)

    const existing = document.head.querySelector('script[data-seo-jsonld="true"]')
    if (existing) existing.remove()
    if (jsonLd) {
      const script = document.createElement('script')
      script.type = 'application/ld+json'
      script.setAttribute('data-seo-jsonld', 'true')
      script.text = JSON.stringify(jsonLd)
      document.head.appendChild(script)
    }

    return () => {
      // leave last meta in place; next page will overwrite
    }
  }, [title, description, path, type, image, robots, JSON.stringify(jsonLd), keywords?.join(',')])

  return null
}
