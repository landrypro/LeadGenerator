export function fileNameSegment(value, fallback = 'export') {
  const normalized = value?.trim().replace(/\s+/g, '-').toLowerCase()
  return normalized || fallback
}


export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
