/**
 * Structured frontend logging.
 *
 * Emits one JSON object per log entry to the browser console so the entries
 * are machine-readable, and forwards error-level entries to the backend
 * (POST /api/v1/logs) so they land in logs/frontend.log together with the
 * backend's app/llm channels.
 *
 * Usage:
 *
 * import { logger } from '@/utils/logger'
 * logger.info('Job form submitted', { jobId, platformCount })
 * logger.error('Publish failed', { status: 502, url, error: err.message })
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogEntry {
  timestamp: string
  level: LogLevel
  service: 'frontend'
  message: string
  requestId?: string
  url?: string
  component?: string
  [key: string]: unknown
}

interface LoggerOptions {
  service?: string
  component?: string
  endpoint?: string
  minLevel?: LogLevel
}

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
}

const CONSOLE_FOR_LEVEL: Record<LogLevel, (...args: unknown[]) => void> = {
  debug: typeof console.debug === 'function' ? console.debug.bind(console) : console.log.bind(console),
  info: console.info.bind(console),
  warn: console.warn.bind(console),
  error: console.error.bind(console),
}

// Redact tokens/codes that may appear in query strings.
const SENSITIVE_PARAMS = /([?&])(code|access_token|refresh_token|password|secret)=[^&]*/gi

export function sanitizeUrl(url?: string): string | undefined {
  if (!url) return url
  return url.replace(SENSITIVE_PARAMS, '$1***')
}

function nowIso(): string {
  return new Date().toISOString()
}

export class FrontendLogger {
  private service: string
  private component?: string
  private endpoint: string
  private minLevel: number
  private requestId: string
  private queue: LogEntry[] = []
  private flushTimer: ReturnType<typeof setTimeout> | null = null
  private readonly MAX_QUEUE = 50
  private readonly FLUSH_INTERVAL_MS = 5000

  constructor(opts: LoggerOptions = {}) {
    this.service = opts.service ?? 'frontend'
    this.component = opts.component
    this.endpoint = opts.endpoint ?? '/api/v1/logs'
    this.minLevel = LEVEL_ORDER[opts.minLevel ?? 'debug']
    this.requestId =
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : 'unknown'

    if (typeof window !== 'undefined') {
      window.addEventListener('pagehide', () => this.flush(), { once: true })
      this.scheduleFlush()
    }
  }

  /** Override the default request id used to correlate frontend/backend logs. */
  setRequestId(requestId: string): void {
    this.requestId = requestId
  }

  log(level: LogLevel, message: string, extra?: Record<string, unknown>): void {
    if (LEVEL_ORDER[level] < this.minLevel) return

    const entry: LogEntry = {
      timestamp: nowIso(),
      level,
      service: 'frontend',
      message,
      requestId: this.requestId,
      component: this.component,
      ...extra,
    }

    // Structured console output (one JSON object per line).
    CONSOLE_FOR_LEVEL[level](JSON.stringify(entry))

    this.queue.push(entry)
    if (this.queue.length >= this.MAX_QUEUE) {
      this.flush()
    } else if (level === 'error') {
      // Errors are flushed immediately (best-effort) so they survive a crash.
      void this.send()
    }
  }

  debug(message: string, extra?: Record<string, unknown>): void {
    this.log('debug', message, extra)
  }

  info(message: string, extra?: Record<string, unknown>): void {
    this.log('info', message, extra)
  }

  warn(message: string, extra?: Record<string, unknown>): void {
    this.log('warn', message, extra)
  }

  error(message: string, extra?: Record<string, unknown>): void {
    this.log('error', message, extra)
  }

  private scheduleFlush(): void {
    if (this.flushTimer !== null) return
    this.flushTimer = setInterval(() => void this.send(), this.FLUSH_INTERVAL_MS)
  }

  private async send(): Promise<void> {
    if (this.queue.length === 0) return
    const batch = { entries: this.queue.splice(0, this.queue.length) }
    try {
      await fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(batch),
      })
      // Best-effort: ignore failures so logging never breaks the UI.
    } catch {
      // Drop the batch if the backend is unreachable.
    }
  }

  /** Flush any queued entries synchronously-best-effort (e.g. on pagehide). */
  flush(): void {
    if (this.queue.length === 0) return
    const batch = { entries: this.queue.splice(0, this.queue.length) }
    try {
      // eslint-disable-next-line no-void
      void navigator.sendBeacon(this.endpoint, JSON.stringify(batch))
    } catch {
      try {
        void fetch(this.endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(batch),
        })
      } catch {
        /* backend unreachable */
      }
    }
  }
}

export const logger = new FrontendLogger()
