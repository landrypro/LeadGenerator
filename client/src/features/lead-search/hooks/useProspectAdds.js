import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

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

  useEffect(() => {
    activeRequestRef.current?.abort()
    setSelectedPlaceIds(new Set())
    setInternalAliases({})
    setItemStates({})
    setAddingIds(new Set())
  }, [selectionToken])

  useEffect(() => () => activeRequestRef.current?.abort(), [])

  const selectedCount = selectedPlaceIds.size
  const adding = addingIds.size > 0
  const selectedReady = selectedCount > 0 && setToArray(selectedPlaceIds).every(
    (placeId) => internalAliases[placeId]?.trim(),
  )

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
    adding,
    togglePlace,
    updateInternalAlias,
    addOne,
    addSelected,
  }), [addOne, addSelected, adding, addingIds, internalAliases, itemStates, selectedCount, selectedPlaceIds, selectedReady, togglePlace, updateInternalAlias])

  return value
}
