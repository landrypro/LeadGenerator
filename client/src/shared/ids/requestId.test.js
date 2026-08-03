import { describe, expect, it, vi } from 'vitest'

import { createRequestId } from './requestId'


describe('createRequestId', () => {
  it('rend la génération UUID injectable et ne la transforme pas', () => {
    const randomUUID = vi.fn().mockReturnValue('request-id-deterministe')
    expect(createRequestId(randomUUID)).toBe('request-id-deterministe')
    expect(randomUUID).toHaveBeenCalledTimes(1)
  })
})
