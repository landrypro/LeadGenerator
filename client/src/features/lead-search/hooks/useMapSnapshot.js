import { useEffect, useState } from 'react'

import { toUserMessage } from '../../../shared/api/errors'
import { leadSearchApi } from '../api/leadSearchApi'


export function useMapSnapshot(searchedAt, resultToken) {
  const [snapshotUrl, setSnapshotUrl] = useState('')
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [snapshotError, setSnapshotError] = useState('')

  useEffect(() => {
    if (!searchedAt || !resultToken) {
      setSnapshotUrl('')
      setSnapshotLoading(false)
      setSnapshotError('')
      return undefined
    }
    const controller = new AbortController()
    let objectUrl = ''
    let active = true
    setSnapshotLoading(true)
    setSnapshotError('')

    leadSearchApi.mapSnapshot(resultToken, controller.signal)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setSnapshotUrl(objectUrl)
      })
      .catch((error) => {
        if (active && error.name !== 'AbortError') {
          setSnapshotError(toUserMessage(error, 'La carte Google est indisponible.'))
        }
      })
      .finally(() => {
        if (active) setSnapshotLoading(false)
      })

    return () => {
      active = false
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [searchedAt, resultToken])

  return { snapshotUrl, snapshotLoading, snapshotError }
}
