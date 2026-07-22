import { useCallback, useState } from 'react'

import { toUserMessage } from '../api/errors'


export function useErrorNotice() {
  const [error, setError] = useState('')
  const clearError = useCallback(() => setError(''), [])
  const reportError = useCallback((cause, fallbackMessage) => {
    setError(toUserMessage(cause, fallbackMessage))
  }, [])
  return { error, clearError, reportError }
}
