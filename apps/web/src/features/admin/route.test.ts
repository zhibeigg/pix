import { describe, expect, it } from 'vitest'
import { buildAdminHash, parseAdminHash } from './route'

describe('admin hash route', () => {
  it('keeps the selected tab and important filters', () => {
    const parsed = parseAdminHash('#/admin?tab=orders&status=paid&q=alice')
    expect(parsed.tab).toBe('orders')
    expect(parsed.params.get('status')).toBe('paid')
    expect(buildAdminHash('users', parsed.params)).toBe('#/admin?tab=users&status=paid&q=alice')
  })

  it('falls back to overview for an illegal tab', () => {
    expect(parseAdminHash('#/admin?tab=definitely-not-valid').tab).toBe('overview')
  })
})
