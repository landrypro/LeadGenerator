import { useEffect, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'
import { leadSearchApi } from '../api/leadSearchApi'


export function useMapSnapshot(generatedAt, resultToken) {
  const [snapshotUrl, setSnapshotUrl] = useState('')
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [snapshotError, setSnapshotError] = useState('')

  useEffect(() => {
    if (!generatedAt || !resultToken) return undefined
    const controller = new AbortController()
    let objectUrl = ''
    setSnapshotLoading(true)
    setSnapshotError('')

    leadSearchApi.mapSnapshot(resultToken, controller.signal)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setSnapshotUrl(objectUrl)
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setSnapshotError(toUserMessage(error, 'La carte Google est indisponible.'))
        }
      })
      .finally(() => setSnapshotLoading(false))

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [generatedAt, resultToken])

  return { snapshotUrl, snapshotLoading, snapshotError }
}
