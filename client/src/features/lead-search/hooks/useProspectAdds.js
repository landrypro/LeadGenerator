import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { leadSearchApi } from '../api/leadSearchApi'


function setToArray(value) {
  return Array.from(value)
}


export function useProspectAdds({ selectionToken, clearError, reportError }) {
  const [selectedPlaceIds, setSelectedPlaceIds] = useState(() => new Set())
  const [internalAliases, setInternalAliases] = useState({})
  const [itemStates, setItemStates] = useState({})
  const [addingIds, setAddingIds] = useState(() => new Set())
  const activeRequestRef = useRef(null)

  useLayoutEffect(() => {
    activeRequestRef.current?.abort()
    setSelectedPlaceIds(new Set())
    setInternalAliases({})
    setItemStates({})
    setAddingIds(new Set())
  }, [selectionToken])

  useEffect(() => () => activeRequestRef.current?.abort(), [])

  const selectedCount = selectedPlaceIds.size
  const adding = addingIds.size > 0
  const firstSelectedMissingAlias = setToArray(selectedPlaceIds).find(
    (placeId) => !internalAliases[placeId]?.trim(),
  ) ?? ''
  const selectedReady = selectedCount > 0 && !firstSelectedMissingAlias

  const updateInternalAlias = useCallback((placeId, value) => {
    setInternalAliases((current) => ({ ...current, [placeId]: value }))
  }, [])

  const togglePlace = useCallback((placeId) => {
    setSelectedPlaceIds((current) => {
      const next = new Set(current)
      if (next.has(placeId)) next.delete(placeId)
      else next.add(placeId)
      return next
    })
  }, [])

  const togglePlaces = useCallback((placeIds) => {
    const requested = Array.from(new Set(placeIds.filter(Boolean)))
    setSelectedPlaceIds((current) => {
      const next = new Set(current)
      const allSelected = requested.length > 0 && requested.every((placeId) => next.has(placeId))
      for (const placeId of requested) {
        if (allSelected) next.delete(placeId)
        else next.add(placeId)
      }
      return next
    })
  }, [])

  const addPlaces = useCallback(async (placeIds) => {
    const requested = Array.from(new Set(placeIds.filter(Boolean)))
    const items = requested.map((placeId) => ({
      place_id: placeId,
      internal_alias: internalAliases[placeId]?.trim() ?? '',
    }))
    if (!selectionToken || !items.length || items.some((item) => !item.internal_alias)) return null
    const controller = new AbortController()
    activeRequestRef.current = controller
    setAddingIds(new Set(requested))
    clearError()
    try {
      const outcome = await leadSearchApi.addGoogleProspects({
        selection_token: selectionToken,
        items,
      }, controller.signal)
      setItemStates((current) => {
        const next = { ...current }
        for (const item of outcome.items ?? []) {
          next[item.place_id] = item.disposition
        }
        return next
      })
      setInternalAliases((current) => {
        const next = { ...current }
        for (const item of outcome.items ?? []) {
          if (item.prospect?.internal_alias) next[item.place_id] = item.prospect.internal_alias
        }
        return next
      })
      setSelectedPlaceIds((current) => {
        const next = new Set(current)
        for (const placeId of requested) next.delete(placeId)
        return next
      })
      return outcome
    } catch (error) {
      if (error?.name !== 'AbortError') {
        reportError(error, 'Impossible d’ajouter la sélection au CRM.')
        setItemStates((current) => {
          const next = { ...current }
          for (const placeId of requested) next[placeId] = 'error'
          return next
        })
      }
      return null
    } finally {
      if (activeRequestRef.current === controller) activeRequestRef.current = null
      setAddingIds(new Set())
    }
  }, [clearError, internalAliases, reportError, selectionToken])

  const addOne = useCallback((placeId) => addPlaces([placeId]), [addPlaces])
  const addSelected = useCallback(() => addPlaces(setToArray(selectedPlaceIds)), [addPlaces, selectedPlaceIds])

  const value = useMemo(() => ({
    selectedPlaceIds,
    internalAliases,
    itemStates,
    addingIds,
    selectedCount,
    selectedReady,
    firstSelectedMissingAlias,
    adding,
    togglePlace,
    togglePlaces,
    updateInternalAlias,
    addOne,
    addSelected,
  }), [addOne, addSelected, adding, addingIds, firstSelectedMissingAlias, internalAliases, itemStates, selectedCount, selectedPlaceIds, selectedReady, togglePlace, togglePlaces, updateInternalAlias])

  return value
}
