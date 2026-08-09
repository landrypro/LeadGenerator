import { useCallback, useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'
import { auditApi } from '../api/auditApi'


export function useAuditEvents(scope) {
  const initialFiltersRef = useRef(createPeriodFilters(30))
  const filtersRef = useRef(initialFiltersRef.current)
  const itemsRef = useRef([])
  const cursorRef = useRef(null)
  const controllerRef = useRef(null)
  const sequenceRef = useRef(0)
  const pendingRef = useRef(false)
  const [filters, setFilters] = useState(initialFiltersRef.current)
  const [items, setItems] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [announcement, setAnnouncement] = useState('')

  const load = useCallback(async ({ reset, nextFilters = filtersRef.current }) => {
    if (!reset && !cursorRef.current) return null
    if (!reset && pendingRef.current) return null
    if (reset) controllerRef.current?.abort()
    const controller = new AbortController()
    const sequence = sequenceRef.current + 1
    sequenceRef.current = sequence
    controllerRef.current = controller
    pendingRef.current = true
    setError('')
    if (reset && itemsRef.current.length) setRefreshing(true)
    else if (reset) setLoading(true)
    else setLoadingMore(true)
    try {
      const loader = scope === 'platform' ? auditApi.listPlatform : auditApi.listTenant
      const page = await loader(nextFilters, reset ? '' : cursorRef.current, 50, controller.signal)
      if (sequenceRef.current !== sequence) return null
      const nextItems = reset ? page.items : deduplicate([...itemsRef.current, ...page.items])
      itemsRef.current = nextItems
      cursorRef.current = page.next_cursor
      setItems(nextItems)
      setNextCursor(page.next_cursor)
      setAnnouncement(
        reset
          ? `${nextItems.length} événement${nextItems.length > 1 ? 's' : ''} chargé${nextItems.length > 1 ? 's' : ''}.`
          : `${page.items.length} événement${page.items.length > 1 ? 's' : ''} supplémentaire${page.items.length > 1 ? 's' : ''}.`,
      )
      return page
    } catch (loadError) {
      if (loadError?.name !== 'AbortError' && sequenceRef.current === sequence) {
        setError(toUserMessage(loadError, 'Impossible de charger le journal d’activité.'))
      }
      return null
    } finally {
      if (sequenceRef.current === sequence) {
        controllerRef.current = null
        pendingRef.current = false
        setLoading(false)
        setRefreshing(false)
        setLoadingMore(false)
      }
    }
  }, [scope])

  const applyFilters = useCallback((nextFilters) => {
    filtersRef.current = nextFilters
    setFilters(nextFilters)
    cursorRef.current = null
    setNextCursor(null)
    return load({ reset: true, nextFilters })
  }, [load])

  const resetFilters = useCallback(() => applyFilters(createPeriodFilters(30)), [applyFilters])

  useEffect(() => {
    load({ reset: true, nextFilters: filtersRef.current })
    return () => {
      sequenceRef.current += 1
      controllerRef.current?.abort()
      pendingRef.current = false
    }
  }, [load])

  return {
    filters,
    items,
    nextCursor,
    loading,
    refreshing,
    loadingMore,
    error,
    announcement,
    applyFilters,
    resetFilters,
    refresh: () => load({ reset: true }),
    loadMore: () => load({ reset: false }),
  }
}


export function createPeriodFilters(days, additions = {}) {
  const occurredTo = new Date()
  const occurredFrom = new Date(occurredTo)
  occurredFrom.setUTCDate(occurredFrom.getUTCDate() - days)
  return {
    occurredFrom: occurredFrom.toISOString(),
    occurredTo: occurredTo.toISOString(),
    action: '',
    entityType: '',
    entityId: '',
    actorId: '',
    ...additions,
  }
}


export function createCustomPeriodFilters(fromDate, toDate, additions = {}) {
  const occurredFrom = new Date(`${fromDate}T00:00:00`)
  const occurredTo = new Date(`${toDate}T00:00:00`)
  occurredTo.setDate(occurredTo.getDate() + 1)
  if (Number.isNaN(occurredFrom.valueOf()) || Number.isNaN(occurredTo.valueOf())) {
    throw new Error('La période personnalisée est invalide.')
  }
  return {
    occurredFrom: occurredFrom.toISOString(),
    occurredTo: occurredTo.toISOString(),
    action: '',
    entityType: '',
    entityId: '',
    actorId: '',
    ...additions,
  }
}


function deduplicate(items) {
  const seen = new Set()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}
