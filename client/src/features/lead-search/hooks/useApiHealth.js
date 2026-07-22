import { useEffect, useState } from 'react'

import { leadSearchApi } from '../api/leadSearchApi'


export function useApiHealth() {
  const [keyReady, setKeyReady] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    leadSearchApi.health(controller.signal)
      .then((data) => setKeyReady(data.google_api_key_configured))
      .catch((error) => {
        if (error.name !== 'AbortError') setKeyReady(false)
      })
    return () => controller.abort()
  }, [])

  return keyReady
}
