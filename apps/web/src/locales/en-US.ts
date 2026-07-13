import { en } from './en'

export const enUS = {
  ...en,
  admin: {
    ...en.admin,
    overview: {
      controls: { label: 'Operations overview query controls', range: 'Time range', granularity: 'Granularity', compare: 'Previous period', timezone: 'Site timezone', updatedAt: 'Updated {{time}}' },
      ranges: { '24h': '24 hours', '7d': '7 days', '14d': '14 days', '30d': '30 days', '90d': '90 days', custom: 'Custom' },
      granularity: { auto: 'Automatic', hour: 'Hourly', day: 'Daily', week: 'Weekly' },
      custom: { title: 'Custom date range', from: 'Start date', to: 'End date', apply: 'Apply', cancel: 'Cancel', hint: 'Start and end dates are inclusive. Latest date: {{date}}. Maximum: 365 days.', errors: { incomplete: 'Choose both a start and end date.', reversed: 'The start date cannot be after the end date.', future: 'The end date cannot be after the site date.', tooLong: 'A custom range cannot exceed 365 days.' } },
      states: { refreshing: 'Refreshing', staleError: 'Refresh failed. Showing the last successful data: {{error}}', retry: 'Retry', emptyTitle: 'No operations data in this period', emptyDescription: 'Expand the range to include earlier jobs, recharges, or user activity.', expandRange: 'Expand to {{range}}' },
      kpis: { label: 'Period key metrics', jobs: 'Jobs', successRate: 'Success rate', creditsConsumed: 'Credits consumed', creditsRecharged: 'Credits recharged', paidOrders: 'Paid orders', activeUsers: 'Active users' },
      comparison: { current: 'Current', previous: 'Previous', unavailable: 'No comparable data', new: 'New', points: '{{value}} percentage points' },
      topics: { quality: 'Job quality', credits: 'Credit flow', orders: 'Order conversion', users: 'User activity' },
      series: { jobs: 'Jobs', success_rate: 'Success rate', credits_recharged: 'Credits recharged', credits_consumed: 'Credits consumed', orders_created: 'New orders', orders_paid: 'Paid orders', active_users: 'Active users', new_users: 'New users' },
      chart: { title: 'Primary trend', description: 'The current period is solid; the previous equal-length period is dashed in the same color.', topicsLabel: 'Trend topic', legendLabel: 'Chart legend; use the keyboard to toggle datasets', currentTime: 'Current time', previousTime: 'Previous time', ariaLabel: '{{topic}} trend for {{range}}. Toggle series with the legend and select points to link bucket details.' },
      diagnostics: { title: 'Period diagnostics', description: 'Quality, funds, and conversion structure.', outcome: 'Succeeded / failed', netCredits: 'Recharge − consumption', paymentRate: 'Order payment rate', payingRate: 'Active-to-paying rate', todayFailureRate: 'Today failure rate {{value}}' },
      realtime: { title: 'Live runtime status', description: 'Current queue and today’s fault diagnostics', pending: 'Queued', running: 'Running', over30m: 'Over 30 minutes', failures: 'Failures today', alerts: 'Policy / upstream / pipeline alerts' },
      ledger: { title: 'Lifetime ledger', description: 'All-time totals retained in the production database', users: 'Users', jobs: 'Jobs', succeeded: 'Succeeded', failed: 'Failed', recharged: 'Recharged', consumed: 'Consumed', orders: 'Orders', paidOrders: 'Paid orders', uploads: 'Uploads' },
      details: { title: 'Bucket details', description: 'Expand to select buckets in either the chart or detail view', columns: { time: 'Time', jobs: 'Jobs / success', credits: 'Recharge / consume', orders: 'New / paid', users: 'Active / new' } },
    },
  },
} as const
