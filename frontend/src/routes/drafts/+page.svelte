<script lang="ts">
  import { onMount } from 'svelte';
  import { FileText, RefreshCw, Edit, CheckCircle2, Pencil, RotateCcw, SkipForward, ExternalLink } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let drafts: any[] = [];
  let accounts: any[] = [];
  let loading = true;
  let error = '';
  let filterStatus = '';
  let editingDraft: string | null = null;
  let editBody = '';
  let postingDraft: string | null = null;
  let posting = false;

  async function fetchData() {
    loading = true;
    error = '';
    try {
      const [draftsRes, accountsRes] = await Promise.all([
        fetchDrafts(),
        fetchAccounts(),
      ]);
      drafts = draftsRes;
      accounts = accountsRes;
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function fetchDrafts() {
    const params = new URLSearchParams();
    if (filterStatus) params.set('status', filterStatus);
    const res = await fetch(`${API_BASE}/api/drafts?${params}`);
    if (!res.ok) throw new Error('Failed to fetch drafts');
    return res.json();
  }

  async function fetchAccounts() {
    const res = await fetch(`${API_BASE}/api/accounts`);
    if (!res.ok) throw new Error('Failed to fetch accounts');
    return res.json();
  }

  async function handleApprove(draftId: string) {
    await fetch(`${API_BASE}/api/drafts/${draftId}/approve`, { method: 'POST' });
    await fetchData();
  }

  async function handlePost(draftId: string, accountId: string) {
    posting = true;
    try {
      await fetch(`${API_BASE}/api/drafts/${draftId}/post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId }),
      });
      await fetchData();
    } finally {
      posting = false;
    }
  }

  async function handleSkip(draftId: string) {
    await fetch(`${API_BASE}/api/drafts/${draftId}/skip`, { method: 'POST' });
    await fetchData();
  }

  async function handleRewrite(draftId: string) {
    const feedback = prompt('Rewrite feedback (optional):');
    await fetch(`${API_BASE}/api/drafts/${draftId}/rewrite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback: feedback || '' }),
    });
    await fetchData();
  }

  async function handleEditSave(draftId: string) {
    await fetch(`${API_BASE}/api/drafts/${draftId}/body`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editBody),
    });
    editingDraft = null;
    editBody = '';
    await fetchData();
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
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-semibold text-foreground">Draft Queue</h1>
      <p class="text-muted-foreground mt-1">AI-drafted replies awaiting your review</p>
    </div>
    <button class="btn btn-secondary btn-sm" on:click={fetchData}>
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
    <!-- Filter -->
    <div class="card p-4">
      <select bind:value={filterStatus} class="input max-w-[200px]">
        <option value="">All Status</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="posted">Posted</option>
        <option value="skipped">Skipped</option>
        <option value="rewriting">Rewriting</option>
      </select>
    </div>

    <!-- Draft List -->
    {#if drafts.length === 0}
      <div class="card p-12 text-center">
        <FileText class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 class="text-lg font-medium text-foreground">No drafts</h3>
        <p class="text-muted-foreground mt-2">The radar will create drafts when it finds relevant threads.</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each drafts as draft (draft.id)}
          <div class="card">
            <div class="p-6">
              <div class="flex items-start justify-between gap-4 mb-3">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="badge {draft.status === 'pending' ? 'badge-yellow' : draft.status === 'approved' ? 'badge-blue' : draft.status === 'posted' ? 'badge-green' : draft.status === 'skipped' ? 'badge-secondary' : 'badge-purple'}">
                    {draft.status || 'pending'}
                  </span>
                  <span class="text-sm text-muted-foreground">{draft.subreddit}</span>
                  <span class="text-xs text-muted-foreground">{timeAgo(draft.created_at)}</span>
                </div>
              </div>

              <h4 class="text-base font-medium text-foreground mb-3">
                <a href={draft.thread_url} target="_blank" rel="noopener" class="hover:text-blue-400 inline-flex items-center gap-1">
                  {draft.thread_title}
                  <ExternalLink class="h-3 w-3" />
                </a>
              </h4>

              {#if editingDraft === draft.id}
                <textarea
                  bind:value={editBody}
                  rows={6}
                  class="input w-full mb-3"
                ></textarea>
                <div class="flex gap-2">
                  <button class="btn btn-primary btn-sm" on:click={() => handleEditSave(draft.id)}>
                    <CheckCircle2 class="h-3 w-3" />
                    Save
                  </button>
                  <button class="btn btn-secondary btn-sm" on:click={() => { editingDraft = null; editBody = ''; }}>
                    Cancel
                  </button>
                </div>
              {:else}
                <div class="bg-secondary/50 rounded-md p-4 mb-3 text-sm text-foreground whitespace-pre-wrap">{draft.body}</div>
              {/if}

              <div class="flex items-center gap-2 flex-wrap">
                {#if draft.status === 'pending' || draft.status === 'rewriting'}
                  <button class="btn btn-secondary btn-sm" on:click={() => { editingDraft = draft.id; editBody = draft.body; }}>
                    <Pencil class="h-3 w-3" />
                    Edit
                  </button>
                  <button class="btn btn-primary btn-sm" on:click={() => handleApprove(draft.id)}>
                    <CheckCircle2 class="h-3 w-3" />
                    Approve
                  </button>
                  <button class="btn btn-secondary btn-sm" on:click={() => handleRewrite(draft.id)}>
                    <RotateCcw class="h-3 w-3" />
                    Rewrite
                  </button>
                  <button class="btn btn-secondary btn-sm" on:click={() => handleSkip(draft.id)}>
                    <SkipForward class="h-3 w-3" />
                    Skip
                  </button>
                {/if}
                {#if draft.status === 'approved'}
                  <select class="input max-w-[250px]" bind:value={postingDraft}>
                    <option value="">Select account to post...</option>
                    {#each accounts as acc}
                      {#if acc.is_active !== false}
                        <option value={acc.username}>{acc.username} (karma: {acc.karma || '?'})</option>
                      {/if}
                    {/each}
                  </select>
                  <button
                    class="btn btn-primary btn-sm"
                    on:click={() => {
                      const sel = document.querySelector('select[value]');
                      if (sel && sel.value) handlePost(draft.id, sel.value);
                    }}
                    disabled={!postingDraft || posting}
                  >
                    {posting ? 'Posting...' : '🚀 Post'}
                  </button>
                {/if}
                <a href={draft.thread_url} target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
                  <ExternalLink class="h-3 w-3" />
                  Thread
                </a>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
