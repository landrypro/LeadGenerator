export function createRequestId(randomUUID = () => crypto.randomUUID()) {
  return randomUUID()
}
