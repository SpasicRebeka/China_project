import { describe, expect, it } from 'vitest'
import { readSessionAuth } from './realtime'

describe('readSessionAuth', () => {
  it('reads a complete local session', () => {
    expect(readSessionAuth('?session=abc&token=secret')).toEqual({ sessionId: 'abc', token: 'secret' })
  })

  it('rejects incomplete credentials', () => {
    expect(readSessionAuth('?session=abc')).toBeNull()
  })
})

