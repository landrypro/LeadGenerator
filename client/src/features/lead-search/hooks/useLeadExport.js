import { useCallback, useState } from 'react'

import { downloadBlob, fileNameSegment } from '../../../shared/browser/download'
import { leadSearchApi } from '../api/leadSearchApi'


export function useLeadExport({ clearError, reportError }) {
  const [exporting, setExporting] = useState(false)

  const exportLeads = useCallback(async (leads, searchParameters) => {
    if (!leads.length) return
    setExporting(true)
    clearError()
    try {
      const blob = await leadSearchApi.export({ leads, search: searchParameters })
      downloadBlob(blob, `leads-${fileNameSegment(searchParameters.query)}.xlsx`)
    } catch (error) {
      reportError(error, 'L’export a échoué.')
    } finally {
      setExporting(false)
    }
  }, [clearError, reportError])

  return { exporting, exportLeads }
}
