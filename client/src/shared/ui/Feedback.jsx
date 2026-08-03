import { useEffect, useRef } from 'react'


export function ErrorBanner({ children, compact = false }) {
  const bannerRef = useRef(null)
  useEffect(() => bannerRef.current?.focus(), [])
  return <div ref={bannerRef} className={`error-banner${compact ? ' compact' : ''}`} role="alert" tabIndex="-1">{children}</div>
}
