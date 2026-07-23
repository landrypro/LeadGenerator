export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

let csrfToken = ''
let unauthorizedHandler = null


export function configureHttpSecurity({ token = '', onUnauthorized = null } = {}) {
  csrfToken = token
  unauthorizedHandler = onUnauthorized
}

async function readErrorMessage(response, fallbackMessage) {
  try {
    const payload = await response.json()
    return payload.error?.message || payload.detail || fallbackMessage
  } catch {
    return fallbackMessage
  }
}

export async function request(path, { responseType = 'json', fallbackMessage = 'La requête a échoué.', ...options } = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = { ...options.headers }
  if (csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    headers['X-CSRF-Token'] = csrfToken
  }
  let response
  try {
    response = await fetch(path, { ...options, credentials: 'same-origin', headers })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new ApiError('Impossible de joindre le serveur.')
  }

  if (!response.ok) {
    if (response.status === 401 && unauthorizedHandler) unauthorizedHandler()
    throw new ApiError(await readErrorMessage(response, fallbackMessage), response.status)
  }
  if (responseType === 'blob') return response.blob()
  if (response.status === 204) return null
  return response.json()
}


export function postJson(path, body, options = {}) {
  return request(path, {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    body: JSON.stringify(body),
  })
}
