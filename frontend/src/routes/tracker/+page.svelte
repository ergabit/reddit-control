<script lang="ts">
  import { onMount } from 'svelte';
  import { BarChart3, TrendingUp, MessageSquare, Eye, ExternalLink } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let selectedClient = localStorage.getItem('reddit-control-client') || 'default';
  let tracker: any[] = [];
  let stats: any = null;
  let loading = true;
  let error = '';

  async function fetchData() {
    loading = true;
    error = '';
    try {
      const [trackerRes, statsRes] = await Promise.all([
        fetchTracker(),
        fetchStats(),
      ]);
      tracker = trackerRes;
      stats = statsRes;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function fetchTracker() {
    const res = await fetch(`${API_BASE}/api/tracker?client_id=${selectedClient}&limit=100`);
    if (!res.ok) throw new Error('Failed to fetch tracker');
    return res.json();
  }

  async function fetchStats() {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  }

  onMount(() => {
    fetchData();
  });

  function timeAgo(ts: number): string {
    if (!ts) return '';
    const diff = Date.now() / 1000 - ts;
    const mins = Math.floor(diff / 60);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }
</script>

<div class="space-y-6">
  <div>
    <h1 class="text-2xl font-semibold text-foreground">Reply Tracker</h1>
    <p class="text-muted-foreground mt-1">Performance metrics for all posted replies</p>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <div class="text-muted-foreground">Loading...</div>
    </div>
  {:else if error}
    <div class="card p-6">
      <p class="text-destructive">{error}</p>
    </div>
  {:else}
    <!-- Summary Stats -->
    <div class="grid gap-4 md:grid-cols-3">
      <div class="card p-6">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-lg bg-emerald-600/10 flex items-center justify-center">
            <TrendingUp class="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <p class="text-sm font-medium text-muted-foreground">Total Upvotes</p>
            <p class="text-2xl font-bold text-foreground">{stats?.tracker?.total_upvotes ?? 0}</p>
          </div>
        </div>
      </div>
      <div class="card p-6">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-lg bg-purple-600/10 flex items-center justify-center">
            <MessageSquare class="h-5 w-5 text-purple-400" />
          </div>
          <div>
            <p class="text-sm font-medium text-muted-foreground">Total Replies</p>
            <p class="text-2xl font-bold text-foreground">{stats?.tracker?.total_replies ?? 0}</p>
          </div>
        </div>
      </div>
      <div class="card p-6">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-lg bg-blue-600/10 flex items-center justify-center">
            <Eye class="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p class="text-sm font-medium text-muted-foreground">Total Clicks</p>
            <p class="text-2xl font-bold text-foreground">{stats?.tracker?.total_clicks ?? 0}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Tracker Table -->
    {#if tracker.length === 0}
      <div class="card p-12 text-center">
        <BarChart3 class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 class="text-lg font-medium text-foreground">No replies tracked</h3>
        <p class="text-muted-foreground mt-2">Replies will appear here once posted.</p>
      </div>
    {:else}
      <div class="card overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b">
              <th class="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Thread</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Account</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Posted</th>
              <th class="text-center py-3 px-4 text-sm font-medium text-muted-foreground">Upvotes</th>
              <th class="text-center py-3 px-4 text-sm font-medium text-muted-foreground">Replies</th>
              <th class="text-center py-3 px-4 text-sm font-medium text-muted-foreground">Clicks</th>
              <th class="text-center py-3 px-4 text-sm font-medium text-muted-foreground">Link</th>
            </tr>
          </thead>
          <tbody>
            {#each tracker as entry}
              <tr class="border-b last:border-0 hover:bg-secondary/50">
                <td class="py-3 px-4">
                  <span class="text-sm text-foreground">{entry.thread_title?.substring(0, 50)}{entry.thread_title?.length > 50 ? '...' : ''}</span>
                </td>
                <td class="py-3 px-4">
                  <span class="text-sm text-muted-foreground">{entry.account_id}</span>
                </td>
                <td class="py-3 px-4">
                  <span class="text-sm text-muted-foreground">{timeAgo(entry.posted_at)}</span>
                </td>
                <td class="py-3 px-4 text-center">
                  <span class="text-sm font-medium text-foreground">{entry.upvotes}</span>
                </td>
                <td class="py-3 px-4 text-center">
                  <span class="text-sm font-medium text-foreground">{entry.replies}</span>
                </td>
                <td class="py-3 px-4 text-center">
                  <span class="text-sm font-medium text-foreground">{entry.clicks}</span>
                </td>
                <td class="py-3 px-4 text-center">
                  <a href={entry.comment_url} target="_blank" rel="noopener" class="btn btn-ghost btn-sm">
                    <ExternalLink class="h-3 w-3" />
                  </a>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>
