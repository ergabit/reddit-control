<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Search,
    FileText,
    Users,
    TrendingUp,
    MessageSquare,
    Eye,
    Plus,
    RefreshCw,
  } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let stats: any = null;
  let threads: any[] = [];
  let drafts: any[] = [];
  let accounts: any[] = [];
  let loading = true;
  let error = '';
  let selectedClient = localStorage.getItem('reddit-control-client') || 'default';

  let filterStatus = '';
  let filterSub = '';
  let editingDraft: string | null = null;
  let editBody = '';
  let postingDraft: string | null = '';
  let posting = false;
  let showAddAccount = false;
  let newAccount = { username: '', password: '', email: '' };

  async function fetchData() {
    loading = true;
    error = '';
    try {
      const [threadsRes, draftsRes, accountsRes, statsRes] = await Promise.all([
        fetchThreads(),
        fetchDrafts(),
        fetchAccounts(),
        fetchStats(),
      ]);
      threads = threadsRes;
      drafts = draftsRes;
      accounts = accountsRes;
      stats = statsRes;
    } catch (e: any) {
      error = e.message || 'Failed to load data';
    } finally {
      loading = false;
    }
  }

  async function fetchThreads() {
    const params = new URLSearchParams({ client_id: selectedClient });
    if (filterStatus) params.set('status', filterStatus);
    if (filterSub) params.set('subreddit', filterSub);
    const res = await fetch(`${API_BASE}/api/threads?${params}`);
    if (!res.ok) throw new Error('Failed to fetch threads');
    return res.json();
  }

  async function fetchDrafts() {
    const res = await fetch(`${API_BASE}/api/drafts?client_id=${selectedClient}`);
    if (!res.ok) throw new Error('Failed to fetch drafts');
    return res.json();
  }

  async function fetchAccounts() {
    const res = await fetch(`${API_BASE}/api/accounts?client_id=${selectedClient}`);
    if (!res.ok) throw new Error('Failed to fetch accounts');
    return res.json();
  }

  async function fetchStats() {
    const res = await fetch(`${API_BASE}/api/stats?client_id=${selectedClient}`);
    if (!res.ok) throw new Error('Failed to fetch stats');
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

  async function handleAddAccount() {
    await fetch(`${API_BASE}/api/accounts?client_id=${selectedClient}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...newAccount, client_id: selectedClient }),
    });
    newAccount = { username: '', password: '', email: '' };
    showAddAccount = false;
    await fetchData();
  }

  onMount(() => {
    fetchData();
    setInterval(fetchData, 30000);
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
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-semibold text-foreground">Dashboard</h1>
      <p class="text-muted-foreground mt-1">Reddit visibility campaign overview</p>
    </div>
    <div class="flex items-center gap-2">
      <button class="btn btn-secondary btn-sm" on:click={fetchData}>
        <RefreshCw class="h-4 w-4" />
        Refresh
      </button>
      <a href="/findings" class="btn btn-primary btn-sm">
        <Plus class="h-4 w-4" />
        New Thread
      </a>
    </div>
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
    <!-- Stats Grid -->
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <div class="card p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-muted-foreground">Threads Found</p>
            <p class="text-2xl font-bold text-foreground mt-1">{stats?.threads_by_status?.new ?? 0}</p>
          </div>
          <div class="h-10 w-10 rounded-lg bg-blue-600/10 flex items-center justify-center">
            <Search class="h-5 w-5 text-blue-400" />
          </div>
        </div>
      </div>
      <div class="card p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-muted-foreground">Pending Drafts</p>
            <p class="text-2xl font-bold text-foreground mt-1">{stats?.drafts_by_status?.pending ?? 0}</p>
          </div>
          <div class="h-10 w-10 rounded-lg bg-yellow-600/10 flex items-center justify-center">
            <FileText class="h-5 w-5 text-yellow-400" />
          </div>
        </div>
      </div>
      <div class="card p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-muted-foreground">Active Accounts</p>
            <p class="text-2xl font-bold text-foreground mt-1">{stats?.active_accounts ?? 0}</p>
          </div>
          <div class="h-10 w-10 rounded-lg bg-emerald-600/10 flex items-center justify-center">
            <Users class="h-5 w-5 text-emerald-400" />
          </div>
        </div>
      </div>
      <div class="card p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium text-muted-foreground">Total Replies</p>
            <p class="text-2xl font-bold text-foreground mt-1">{stats?.tracker?.total ?? 0}</p>
          </div>
          <div class="h-10 w-10 rounded-lg bg-purple-600/10 flex items-center justify-center">
            <MessageSquare class="h-5 w-5 text-purple-400" />
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="grid gap-4 md:grid-cols-2">
      <div class="card">
        <div class="card-header">
          <div class="flex items-center gap-2">
            <TrendingUp class="h-5 w-5 text-emerald-400" />
            <h2 class="card-title">Engagement</h2>
          </div>
          <p class="card-description">Performance metrics across all posts</p>
        </div>
        <div class="card-content">
          <div class="grid grid-cols-3 gap-4">
            <div class="text-center">
              <p class="text-2xl font-bold text-foreground">{stats?.tracker?.total_upvotes ?? 0}</p>
              <p class="text-xs text-muted-foreground mt-1">Upvotes</p>
            </div>
            <div class="text-center">
              <p class="text-2xl font-bold text-foreground">{stats?.tracker?.total_replies ?? 0}</p>
              <p class="text-xs text-muted-foreground mt-1">Replies</p>
            </div>
            <div class="text-center">
              <p class="text-2xl font-bold text-foreground">{stats?.tracker?.total_clicks ?? 0}</p>
              <p class="text-xs text-muted-foreground mt-1">Clicks</p>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h2 class="card-title">Quick Actions</h2>
          <p class="card-description">Common tasks and shortcuts</p>
        </div>
        <div class="card-content">
          <div class="space-y-3">
            <a href="/findings" class="flex items-center gap-3 p-3 rounded-lg border bg-secondary/50 hover:bg-secondary transition-colors">
              <Search class="h-4 w-4 text-blue-400" />
              <span class="text-sm text-foreground">Browse Findings</span>
            </a>
            <a href="/drafts" class="flex items-center gap-3 p-3 rounded-lg border bg-secondary/50 hover:bg-secondary transition-colors">
              <FileText class="h-4 w-4 text-yellow-400" />
              <span class="text-sm text-foreground">Review Drafts</span>
            </a>
            <a href="/accounts" class="flex items-center gap-3 p-3 rounded-lg border bg-secondary/50 hover:bg-secondary transition-colors">
              <Users class="h-4 w-4 text-emerald-400" />
              <span class="text-sm text-foreground">Manage Accounts</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>
