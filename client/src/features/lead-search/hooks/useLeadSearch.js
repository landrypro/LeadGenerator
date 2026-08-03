import { useCallback, useEffect, useRef, useState } from 'react'

import { leadSearchApi } from '../api/leadSearchApi'


export function useLeadSearch({ clearError, reportError }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const activeRequestRef = useRef(null)
  const requestSequenceRef = useRef(0)

  useEffect(() => () => {
    requestSequenceRef.current += 1
    activeRequestRef.current?.abort()
  }, [])

  const runSearch = useCallback(async (form) => {
    activeRequestRef.current?.abort()
    const controller = new AbortController()
    const requestSequence = requestSequenceRef.current + 1
    requestSequenceRef.current = requestSequence
    activeRequestRef.current = controller
    setLoading(true)
    clearError()
    try {
      const data = await leadSearchApi.search({ ...form }, controller.signal)
      if (requestSequenceRef.current !== requestSequence) return null
      setResult(data)
      return data
    } catch (error) {
      if (error?.name !== 'AbortError' && requestSequenceRef.current === requestSequence) {
        reportError(error, 'Impossible de joindre le serveur.')
      }
      return null
    } finally {
      if (requestSequenceRef.current === requestSequence) {
        activeRequestRef.current = null
        setLoading(false)
      }
    }
  }, [clearError, reportError])

  return { result, loading, runSearch }
}
