import { useCallback, useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'


export function usePaginatedResource({ enabled = true, fallbackMessage, keyOf, loader }) {
  const [items, setItems] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [loading, setLoading] = useState(enabled)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const controllerRef = useRef(null)
  const sequenceRef = useRef(0)
  const pendingRef = useRef(null)
  const itemsRef = useRef([])
  const cursorRef = useRef(null)

  const replaceItems = useCallback((updater) => {
    setItems((current) => {
      const next = typeof updater === 'function' ? updater(current) : updater
      itemsRef.current = next
      return next
    })
  }, [])

  const load = useCallback((reset = true) => {
    if (!enabled) return Promise.resolve(null)
    if (pendingRef.current) return pendingRef.current
    if (!reset && !cursorRef.current) return Promise.resolve(null)

    const controller = new AbortController()
    const sequence = sequenceRef.current + 1
    const cursor = reset ? '' : cursorRef.current
    sequenceRef.current = sequence
    controllerRef.current = controller
    setError('')
    if (reset && itemsRef.current.length) setRefreshing(true)
    else if (reset) setLoading(true)
    else setLoadingMore(true)

    const pending = (async () => {
      try {
        const page = await loader(cursor, 25, controller.signal)
        if (sequenceRef.current !== sequence) return null
        const nextItems = reset ? page.items : deduplicate([...itemsRef.current, ...page.items], keyOf)
        replaceItems(nextItems)
        cursorRef.current = page.next_cursor
        setNextCursor(page.next_cursor)
        return page
      } catch (loadError) {
        if (loadError?.name !== 'AbortError' && sequenceRef.current === sequence) {
          setError(toUserMessage(loadError, fallbackMessage))
        }
        return null
      } finally {
        if (sequenceRef.current === sequence) {
          controllerRef.current = null
          pendingRef.current = null
          setLoading(false)
          setRefreshing(false)
          setLoadingMore(false)
        }
      }
    })()
    pendingRef.current = pending
    return pending
  }, [enabled, fallbackMessage, keyOf, loader, replaceItems])

  useEffect(() => {
    if (enabled) load(true)
    else {
      replaceItems([])
      cursorRef.current = null
      setNextCursor(null)
      setLoading(false)
    }
    return () => {
      sequenceRef.current += 1
      controllerRef.current?.abort()
      pendingRef.current = null
    }
  }, [enabled, load, replaceItems])

  return {
    items,
    setItems: replaceItems,
    nextCursor,
    loading,
    refreshing,
    loadingMore,
    error,
    refresh: () => load(true),
    loadMore: () => load(false),
  }
}


function deduplicate(items, keyOf) {
  const seen = new Set()
  return items.filter((item) => {
    const key = keyOf(item)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
