import { useEffect, useRef, useState } from 'react'

import { leadSearchApi } from '../api/leadSearchApi'


function errorMessage(error, copy) {
  if (error?.code === 'google_location_rate_limited') return copy.locationRateLimit
  if (error?.code === 'invalid_location_selection') return copy.locationExpired
  return copy.locationError
}


export function LocationAutocomplete({ id, label, hint, value, area = '', countryCode = '', disabled = false, selected = false, scope, locale, copy, onChange, onSelect }) {
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [busy, setBusy] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')
  const sessionRef = useRef(null)
  const sequenceRef = useRef(0)
  const resolveControllerRef = useRef(null)

  useEffect(() => () => resolveControllerRef.current?.abort(), [])

  useEffect(() => {
    const text = value.trim()
    if (text.length < 3 || !open) {
      setItems([])
      setSearched(false)
      return undefined
    }
    const controller = new AbortController()
    const sequence = ++sequenceRef.current
    const timer = setTimeout(async () => {
      setBusy(true)
      setError('')
      setSearched(false)
      try {
        sessionRef.current ||= crypto.randomUUID()
        const response = await leadSearchApi.suggestLocation({
          text, area: area.slice(0, 120), scope, language: locale === 'en-CA' ? 'en' : 'fr', country_code: countryCode,
          session_token: sessionRef.current,
        }, controller.signal)
        if (sequence === sequenceRef.current) {
          setItems(response.items || [])
          setSearched(true)
        }
      } catch (cause) {
        if (cause?.name !== 'AbortError' && sequence === sequenceRef.current) {
          setItems([])
          setError(errorMessage(cause, copy))
        }
      } finally {
        if (sequence === sequenceRef.current) setBusy(false)
      }
    }, 400)
    return () => { clearTimeout(timer); controller.abort() }
  }, [value, area, countryCode, scope, locale, open, copy])

  async function choose(item) {
    const sequence = sequenceRef.current
    resolveControllerRef.current?.abort()
    const controller = new AbortController()
    resolveControllerRef.current = controller
    setOpen(false)
    setItems([])
    setBusy(true)
    setError('')
    try {
      const location = await leadSearchApi.resolveLocation({ selection_token: item.selection_token }, controller.signal)
      if (sequence === sequenceRef.current) {
        onSelect(location)
        sessionRef.current = null
      }
    } catch (cause) {
      if (cause?.name !== 'AbortError' && sequence === sequenceRef.current) setError(errorMessage(cause, copy))
    } finally {
      if (sequence === sequenceRef.current) setBusy(false)
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape') { setOpen(false); setItems([]); return }
    if (!items.length) return
    if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); setActive((index) => (index + 1) % items.length) }
    if (event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setActive((index) => index < 0 ? items.length - 1 : (index + items.length - 1) % items.length) }
    if (event.key === 'Enter' && open && active >= 0) { event.preventDefault(); void choose(items[active]) }
  }

  return <div className="location-field" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
  }}>
    <label htmlFor={id}>{label}</label>
    <input
      id={id} role="combobox" autoComplete="off" aria-autocomplete="list"
      aria-expanded={open && items.length > 0} aria-controls={`${id}-suggestions`}
      aria-activedescendant={active >= 0 && open ? `${id}-option-${active}` : undefined}
      disabled={disabled} maxLength={80} value={value} onChange={(event) => {
        resolveControllerRef.current?.abort()
        sequenceRef.current += 1
        onChange(event.target.value)
        setOpen(true)
        setActive(-1)
        setItems([])
        setSearched(false)
      }} onFocus={() => setOpen(!selected)} onKeyDown={handleKeyDown}
    />
    {hint && <small>{hint}</small>}
    {busy && <small role="status">{copy.locationLoading}</small>}
    {error && <small role="alert" className="location-error">{error}</small>}
    {open && searched && !busy && !error && items.length === 0 && <small role="status">{copy.noLocationMatches}</small>}
    {open && items.length > 0 && <div id={`${id}-suggestions`} role="listbox" className="location-suggestions">
      {items.map((item, index) => <button
        id={`${id}-option-${index}`} key={item.selection_token} type="button" role="option"
        aria-selected={index === active} onMouseDown={(event) => event.preventDefault()}
        onClick={() => void choose(item)}
      >{item.label}</button>)}
      <div className="location-attribution" translate="no">Google Maps</div>
    </div>}
  </div>
}
