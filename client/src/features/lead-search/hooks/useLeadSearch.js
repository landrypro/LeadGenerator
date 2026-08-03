import { useCallback, useState } from 'react'

import { leadSearchApi } from '../api/leadSearchApi'


export function useLeadSearch({ clearError, reportError }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const runSearch = useCallback(async (form) => {
    setLoading(true)
    clearError()
    try {
      const data = await leadSearchApi.search({ ...form })
      setResult(data)
      return data
    } catch (error) {
      reportError(error, 'Impossible de joindre le serveur.')
      return null
    } finally {
      setLoading(false)
    }
  }, [clearError, reportError])

  return { result, loading, runSearch }
}
