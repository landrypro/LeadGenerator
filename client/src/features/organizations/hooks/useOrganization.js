import { useCallback, useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'
import { organizationApi } from '../api/organizationApi'


export function useOrganization() {
  const [organization, setOrganization] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const controllerRef = useRef(null)
  const requestSequenceRef = useRef(0)

  const load = useCallback(async () => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    const sequence = requestSequenceRef.current + 1
    requestSequenceRef.current = sequence
    controllerRef.current = controller
    setLoading(true)
    setError('')
    try {
      const data = await organizationApi.get(controller.signal)
      if (requestSequenceRef.current !== sequence) return null
      setOrganization(data)
      return data
    } catch (loadError) {
      if (loadError?.name !== 'AbortError' && requestSequenceRef.current === sequence) {
        setError(toUserMessage(loadError, 'Impossible de charger l’organisation.'))
      }
      return null
    } finally {
      if (requestSequenceRef.current === sequence) {
        controllerRef.current = null
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    load()
    return () => {
      requestSequenceRef.current += 1
      controllerRef.current?.abort()
    }
  }, [load])

  return { organization, setOrganization, loading, error, load }
}
