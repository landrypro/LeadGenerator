const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/


export function extractInvitationToken(browserWindow) {
  const fragment = browserWindow.location.hash.slice(1)
  const parameters = new URLSearchParams(fragment)
  const token = parameters.get('token') || ''
  if (fragment) {
    browserWindow.history.replaceState(
      browserWindow.history.state,
      '',
      `${browserWindow.location.pathname}${browserWindow.location.search}`,
    )
  }
  return TOKEN_PATTERN.test(token) ? token : ''
}
