<script lang="ts">
  import { onMount } from 'svelte';
  import { Search, RefreshCw, ExternalLink, MessageCircle } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let selectedClient = localStorage.getItem('reddit-control-client') || 'default';
  let threads: any[] = [];
  let loading = true;
  let error = '';
  let filterStatus = '';
  let filterSub = '';

  async function fetchThreads() {
    const params = new URLSearchParams({ client_id: selectedClient });
    if (filterStatus) params.set('status', filterStatus);
    if (filterSub) params.set('subreddit', filterSub);
    const res = await fetch(`${API_BASE}/api/threads?${params}`);
    if (!res.ok) throw new Error('Failed to fetch threads');
    return res.json();
  }

  onMount(() => {
    fetchThreads().then(t => { threads = t; loading = false; }).catch(e => { error = e.message; loading = false; });
  });

  function scoreColor(s: number): string {
    if (s >= 75) return '#3fb950';
    if (s >= 60) return '#d29922';
    if (s >= 40) return '#f85149';
    return '#8b949e';
  }

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
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-semibold text-foreground">Thread Findings</h1>
      <p class="text-muted-foreground mt-1">Relevant Reddit threads for iSearchFrom</p>
    </div>
    <button class="btn btn-secondary btn-sm" on:click={() => location.reload()}>
      <RefreshCw class="h-4 w-4" />
      Refresh
    </button>
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
    <!-- Filters -->
    <div class="card p-4">
      <div class="flex gap-4">
        <select bind:value={filterStatus} class="input max-w-[200px]">
          <option value="">All Status</option>
          <option value="new">New</option>
          <option value="digested">Digested</option>
          <option value="alerted">Alerted</option>
          <option value="posted">Posted</option>
          <option value="skipped">Skipped</option>
        </select>
        <input
          type="text"
          placeholder="Filter subreddit..."
          bind:value={filterSub}
          class="input max-w-[200px]"
        />
      </div>
    </div>

    <!-- Thread List -->
    {#if threads.length === 0}
      <div class="card p-12 text-center">
        <Search class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 class="text-lg font-medium text-foreground">No threads found</h3>
        <p class="text-muted-foreground mt-2">Run a radar sweep to find relevant threads.</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each threads as thread (thread.id)}
          <div class="card">
            <div class="p-6">
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-2 flex-wrap">
                    <span class="badge {thread.status === 'new' ? 'badge-blue' : thread.status === 'alerted' ? 'badge-red' : thread.status === 'posted' ? 'badge-green' : 'badge-secondary'}">
                      {thread.status || 'new'}
                    </span>
                    <span class="text-sm text-blue-400 font-medium">{thread.subreddit}</span>
                    <span class="text-xs text-muted-foreground">{timeAgo(thread.created_at)}</span>
                  </div>
                  <h3 class="text-lg font-medium text-foreground">
                    <a href={thread.url} target="_blank" rel="noopener" class="hover:text-blue-400 inline-flex items-center gap-1">
                      {thread.title}
                      <ExternalLink class="h-3 w-3" />
                    </a>
                  </h3>
                  <p class="text-sm text-muted-foreground mt-2 line-clamp-2">{thread.body_preview}</p>
                </div>
                <div class="flex flex-col items-end gap-2 flex-shrink-0">
                  <div class="flex items-center gap-2">
                    <div class="w-24 h-2 bg-secondary rounded-full overflow-hidden">
                      <div class="h-full rounded-full" style="width: {Math.min(thread.score_radar || 0, 100)}%; background: {scoreColor(thread.score_radar || 0)}"></div>
                    </div>
                    <span class="text-sm font-medium text-foreground">{Math.round(thread.score_radar || 0)}</span>
                  </div>
                  <div class="flex items-center gap-3 text-sm text-muted-foreground">
                    <span class="flex items-center gap-1">
                      <MessageCircle class="h-3 w-3" />
                      {thread.num_comments || 0}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2 mt-4">
                <a href={thread.url} target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
                  <ExternalLink class="h-3 w-4" />
                  View on Reddit
                </a>
                <a href="/drafts" class="btn btn-primary btn-sm">
                  <MessageCircle class="h-3 w-4" />
                  Reply
                </a>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
