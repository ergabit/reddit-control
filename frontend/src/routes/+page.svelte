<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { API } from '$lib/constants';

  // ── State ────────────────────────────────────────────────────────
  let activeTab = 'findings' as string;
  let threads: any[] = [];
  let drafts: any[] = [];
  let accounts: any[] = [];
  let stats: any = {};
  let config: any = {};
  let loading = true;
  let error = '';

  // Filters
  let filterStatus = '';
  let filterSub = '';
  let filterMinScore = '';

  // Draft editing
  let editingDraft: any = null;
  let editBody = '';
  let showAddAccount = false;
  let newAccount = { username: '', password: '', email: '' };
  let showAddThread = false;
  let newThread: any = {};

  // Auto-post draft
  let postingDraft: any = null;
  let posting = false;

  // SSE connection
  let eventSource: EventSource | null = null;

  // ── Fetch data ───────────────────────────────────────────────────
  async function fetchData() {
    loading = true;
    error = '';
    try {
      const [threadsRes, draftsRes, accountsRes, statsRes, configRes] = await Promise.all([
        fetchThreads(),
        fetchDrafts(),
        fetchAccounts(),
        fetchStats(),
        fetchConfig(),
      ]);
      threads = threadsRes;
      drafts = draftsRes;
      accounts = accountsRes;
      stats = statsRes;
      config = configRes;
    } catch (e: any) {
      error = e.message || 'Failed to load data';
    } finally {
      loading = false;
    }
  }

  async function fetchThreads() {
    const params = new URLSearchParams();
    if (filterStatus) params.set('status', filterStatus);
    if (filterSub) params.set('subreddit', filterSub);
    if (filterMinScore) params.set('min_score', filterMinScore);
    const res = await fetch(`${API}/api/threads?${params}`);
    if (!res.ok) throw new Error('Failed to fetch threads');
    return res.json();
  }

  async function fetchDrafts() {
    const res = await fetch(`${API}/api/drafts`);
    if (!res.ok) throw new Error('Failed to fetch drafts');
    return res.json();
  }

  async function fetchAccounts() {
    const res = await fetch(`${API}/api/accounts`);
    if (!res.ok) throw new Error('Failed to fetch accounts');
    return res.json();
  }

  async function fetchStats() {
    const res = await fetch(`${API}/api/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  }

  async function fetchConfig() {
    const res = await fetch(`${API}/api/config`);
    if (!res.ok) throw new Error('Failed to fetch config');
    return res.json();
  }

  // ── Actions ──────────────────────────────────────────────────────
  async function handleApprove(draftId: string) {
    await fetch(`${API}/api/drafts/${draftId}/approve`, { method: 'POST' });
    await fetchData();
  }

  async function handlePost(draftId: string, accountId: string) {
    postingDraft = draftId;
    try {
      await fetch(`${API}/api/drafts/${draftId}/post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId }),
      });
      await fetchData();
    } finally {
      postingDraft = null;
    }
  }

  async function handleSkip(draftId: string) {
    await fetch(`${API}/api/drafts/${draftId}/skip`, { method: 'POST' });
    await fetchData();
  }

  async function handleRewrite(draftId: string, feedback: string) {
    await fetch(`${API}/api/drafts/${draftId}/rewrite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback }),
    });
    await fetchData();
  }

  async function handleEditSave(draftId: string) {
    await fetch(`${API}/api/drafts/${draftId}/body`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editBody),
    });
    editingDraft = null;
    editBody = '';
    await fetchData();
  }

  async function handleAddAccount() {
    await fetch(`${API}/api/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newAccount),
    });
    newAccount = { username: '', password: '', email: '' };
    showAddAccount = false;
    await fetchData();
  }

  async function handleToggleAuto() {
    const newMode = !config.auto_mode;
    await fetch(`${API}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_mode: newMode }),
    });
    config.auto_mode = newMode;
  }

  async function handleThresholdChange(val: number) {
    await fetch(`${API}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auto_threshold: val }),
    });
    config.auto_threshold = val;
  }

  // ── SSE ──────────────────────────────────────────────────────────
  function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`${API}/events`);

    eventSource.addEventListener('thread_new', () => fetchData());
    eventSource.addEventListener('draft_new', () => fetchData());
    eventSource.addEventListener('draft_approved', () => fetchData());
    eventSource.addEventListener('draft_posted', () => fetchData());
    eventSource.addEventListener('draft_skipped', () => fetchData());
    eventSource.addEventListener('draft_rewriting', () => fetchData());
    eventSource.addEventListener('draft_updated', () => fetchData());
    eventSource.addEventListener('account_added', () => fetchData());
    eventSource.addEventListener('config_changed', async () => { config = await fetchConfig(); });
    eventSource.addEventListener('radar_imported', () => fetchData());
    eventSource.addEventListener('ping', () => {});

    eventSource.onerror = () => {
      console.warn('SSE connection error, reconnecting...');
      eventSource = null;
      setTimeout(connectSSE, 5000);
    };
  }

  // ── Lifecycle ────────────────────────────────────────────────────
  let trackerData: any[] = [];

  async function fetchTracker() {
    try {
      const res = await fetch(`${API}/api/tracker?limit=100`);
      if (res.ok) trackerData = await res.json();
    } catch (e) { /* ignore */ }
  }

  onMount(() => {
    fetchData();
    fetchTracker();
    connectSSE();
    setInterval(fetchData, 30000);
    setInterval(fetchTracker, 60000);
  });

  onDestroy(() => {
    if (eventSource) eventSource.close();
  });

  // ── Helpers ──────────────────────────────────────────────────────
  function scoreColor(s: number): string {
    if (s >= 75) return '#3fb950';
    if (s >= 60) return '#d29922';
    if (s >= 40) return '#f85149';
    return '#8b949e';
  }

  function scoreLabel(s: number): string {
    if (s >= 80) return '🔥 Critical';
    if (s >= 70) return '⚡ Hot';
    if (s >= 60) return '📌 Good';
    if (s >= 40) return '👍 Relevant';
    return '📎 Low';
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

  function formatNum(n: number): string {
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return String(n);
  }
</script>

<svelte:head>
  <title>iSearchFrom — Reddit Control</title>
  <link rel="stylesheet" href="/app.css" />
</svelte:head>

<div class="app">
  <!-- Header -->
  <header class="header">
    <div class="header-left">
      <h1 class="logo">🎯 Reddit Control</h1>
      <span class="subtitle">iSearchFrom Visibility Campaign</span>
    </div>
    <div class="header-right">
      <!-- Mode toggle -->
      <div class="mode-toggle">
        <span class="mode-label">Supervised</span>
        <button
          class="toggle-switch"
          class:toggle-on={config.auto_mode}
          on:click={handleToggleAuto}
        >
          <span class="toggle-knob"></span>
        </button>
        <span class="mode-label">Auto</span>
      </div>
      {#if config.auto_mode}
        <div class="threshold-control">
          <label>Threshold:</label>
          <input
            type="range"
            min="40"
            max="90"
            step="5"
            value={config.auto_threshold}
            on:input={(e) => handleThresholdChange(Number(e.currentTarget.value))}
          />
          <span class="threshold-value">{config.auto_threshold}</span>
        </div>
      {/if}
      <button class="btn btn-sm" on:click={fetchData}>🔄 Refresh</button>
    </div>
  </header>

  <!-- Main content -->
  <div class="main">
    <!-- Sidebar -->
    <aside class="sidebar">
      <nav class="nav">
        <button
          class="nav-item"
          class:nav-active={activeTab === 'findings'}
          on:click={() => activeTab = 'findings'}
        >
          🔍 Findings
          {#if stats.threads_by_status}
            <span class="nav-badge">{(stats.threads_by_status['new'] || 0) + (stats.threads_by_status['alerted'] || 0)}</span>
          {/if}
        </button>
        <button
          class="nav-item"
          class:nav-active={activeTab === 'drafts'}
          on:click={() => activeTab = 'drafts'}
        >
          📝 Drafts
          {#if stats.drafts_by_status}
            <span class="nav-badge">{(stats.drafts_by_status['pending'] || 0)}</span>
          {/if}
        </button>
        <button
          class="nav-item"
          class:nav-active={activeTab === 'accounts'}
          on:click={() => activeTab = 'accounts'}
        >
          👥 Accounts
        </button>
        <button
          class="nav-item"
          class:nav-active={activeTab === 'tracker'}
          on:click={() => activeTab = 'tracker'}
        >
          📊 Tracker
        </button>
        <button
          class="nav-item"
          class:nav-active={activeTab === 'settings'}
          on:click={() => activeTab = 'settings'}
        >
          ⚙️ Settings
        </button>
      </nav>

      <!-- KPI cards -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-value">{stats.tracker?.total || 0}</div>
          <div class="kpi-label">Replies Posted</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{stats.tracker?.total_upvotes || 0}</div>
          <div class="kpi-label">Upvotes</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{stats.tracker?.total_clicks || 0}</div>
          <div class="kpi-label">UTM Clicks</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{stats.active_accounts || 0}</div>
          <div class="kpi-label">Active Accounts</div>
        </div>
      </div>
    </aside>

    <!-- Content panels -->
    <main class="content">
      {#if loading}
        <div class="loading">Loading...</div>
      {:else if error}
        <div class="error">{error}</div>
      {:else}
        <!-- FINDINGS TAB -->
        {#if activeTab === 'findings'}
          <div class="panel">
            <div class="panel-header">
              <h2>🔍 Thread Findings</h2>
              <div class="filters">
                <select bind:value={filterStatus}>
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
                />
                <input
                  type="number"
                  placeholder="Min score..."
                  bind:value={filterMinScore}
                  style="width: 120px"
                />
              </div>
            </div>

            <div class="thread-list">
              {#each threads as thread (thread.id)}
                <div class="thread-card">
                  <div class="thread-header">
                    <div class="thread-meta">
                      <span class="tag tag-{thread.status || 'new'}">{thread.status || 'new'}</span>
                      <span class="sub">{thread.subreddit}</span>
                      <span class="time">{timeAgo(thread.created_at)}</span>
                    </div>
                    <div class="thread-score">
                      <div class="score-bar">
                        <div
                          class="score-fill"
                          style="width: {Math.min(thread.score_radar || 0, 100)}%; background: {scoreColor(thread.score_radar || 0)}"
                        ></div>
                      </div>
                      <span class="score-value">{Math.round(thread.score_radar || 0)}</span>
                    </div>
                  </div>
                  <h3 class="thread-title">
                    <a href={thread.url} target="_blank" rel="noopener">{thread.title}</a>
                  </h3>
                  <div class="thread-body">{thread.body_preview?.substring(0, 200)}{thread.body_preview?.length > 200 ? '...' : ''}</div>
                  <div class="thread-actions">
                    <span class="thread-stat">💬 {thread.num_comments || 0}</span>
                    {#if thread.topic}
                      <span class="tag tag-pending">{thread.topic}</span>
                    {/if}
                    <a href={thread.url} target="_blank" rel="noopener" class="btn btn-sm">View on Reddit</a>
                  </div>
                </div>
              {/each}
              {#if threads.length === 0}
                <div class="empty-state">No threads found. Run a radar sweep to find relevant threads.</div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- DRAFTS TAB -->
        {#if activeTab === 'drafts'}
          <div class="panel">
            <div class="panel-header">
              <h2>📝 Draft Queue</h2>
              <div class="filters">
                <select bind:value={filterStatus}>
                  <option value="">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="posted">Posted</option>
                  <option value="skipped">Skipped</option>
                  <option value="rewriting">Rewriting</option>
                </select>
              </div>
            </div>

            <div class="draft-list">
              {#each drafts as draft (draft.id)}
                <div class="draft-card">
                  <div class="draft-header">
                    <span class="tag tag-{draft.status || 'pending'}">{draft.status || 'pending'}</span>
                    <span class="sub">{draft.subreddit}</span>
                    <span class="time">{timeAgo(draft.created_at)}</span>
                  </div>
                  <h4 class="draft-thread-title">
                    <a href={draft.thread_url} target="_blank" rel="noopener">{draft.thread_title}</a>
                  </h4>

                  {#if editingDraft === draft.id}
                    <textarea
                      bind:value={editBody}
                      rows={6}
                      class="draft-edit"
                    ></textarea>
                    <div class="draft-edit-actions">
                      <button class="btn btn-primary btn-sm" on:click={() => handleEditSave(draft.id)}>💾 Save</button>
                      <button class="btn btn-sm" on:click={() => { editingDraft = null; editBody = ''; }}>Cancel</button>
                    </div>
                  {:else}
                    <div class="draft-body">{draft.body}</div>
                  {/if}

                  <div class="draft-actions">
                    {#if draft.status === 'pending' || draft.status === 'rewriting'}
                      <button class="btn btn-primary btn-sm" on:click={() => { editingDraft = draft.id; editBody = draft.body; }}>✏️ Edit</button>
                      <button class="btn btn-sm" on:click={() => handleApprove(draft.id)}>✅ Approve</button>
                      <button class="btn btn-sm" on:click={() => {
                        const fb = prompt('Rewrite feedback:');
                        if (fb) handleRewrite(draft.id, fb);
                      }}>🔄 Rewrite</button>
                      <button class="btn btn-sm" on:click={() => handleSkip(draft.id)}>⏭ Skip</button>
                    {/if}
                    {#if draft.status === 'approved'}
                      <select class="btn btn-sm" bind:value={postingDraft}>
                        <option value="">Select account to post...</option>
                        {#each accounts as acc}
                          {#if acc.is_active !== false}
                            <option value={acc.username}>{acc.username} (karma: {acc.karma || '?'}, mentions: {acc.product_mentions}/{acc.total_mentions})</option>
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
                        {postingDraft === draft.id ? '⏳ Posting...' : '🚀 Post'}
                      </button>
                    {/if}
                    <a href={draft.thread_url} target="_blank" rel="noopener" class="btn btn-sm">🔗 Thread</a>
                  </div>
                </div>
              {/each}
              {#if drafts.length === 0}
                <div class="empty-state">No drafts. The radar will create drafts when it finds relevant threads.</div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- ACCOUNTS TAB -->
        {#if activeTab === 'accounts'}
          <div class="panel">
            <div class="panel-header">
              <h2>👥 Accounts</h2>
              <button class="btn btn-primary btn-sm" on:click={() => showAddAccount = !showAddAccount}>
                + Add Account
              </button>
            </div>

            {#if showAddAccount}
              <div class="card mt-16">
                <h3>Add New Account</h3>
                <div class="grid-3 mt-8">
                  <input placeholder="Username" bind:value={newAccount.username} />
                  <input type="password" placeholder="Password" bind:value={newAccount.password} />
                  <input placeholder="Email (optional)" bind:value={newAccount.email} />
                </div>
                <div class="mt-8">
                  <button class="btn btn-primary btn-sm" on:click={handleAddAccount}>Add</button>
                  <button class="btn btn-sm" on:click={() => showAddAccount = false}>Cancel</button>
                </div>
              </div>
            {/if}

            <div class="account-list">
              {#each accounts as acc}
                <div class="card">
                  <div class="flex-between mb-8">
                    <div>
                      <strong>@{acc.username}</strong>
                      {#if !acc.is_active}
                        <span class="tag tag-skipped">Inactive</span>
                      {/if}
                    </div>
                    <div class="flex-between gap-8">
                      <span class="text-sm text-muted">Karma: {acc.karma || '?'}</span>
                      <span class="text-sm text-muted">Ban risk: {Math.round((acc.ban_risk || 0) * 100)}%</span>
                    </div>
                  </div>
                  <div class="grid-3 text-sm">
                    <div>Posts today: <strong>{acc.post_count_today || 0}</strong>/{config.max_posts_per_day || 8}</div>
                    <div>Comments today: <strong>{acc.comment_count_today || 0}</strong>/{config.max_comments_per_day || 25}</div>
                    <div>Mentions: <strong>{acc.product_mentions || 0}</strong>/{acc.total_mentions || 0}</div>
                  </div>
                  <div class="mt-8">
                    <button class="btn btn-sm" on:click={() => handleAddAccount()}>🔄 Refresh</button>
                    <button class="btn btn-sm btn-danger" on:click={() => {
                      if (confirm(`Delete @${acc.username}?`)) {
                        fetch(`${API}/api/accounts/${acc.username}`, { method: 'DELETE' }).then(fetchData);
                      }
                    }}>🗑 Delete</button>
                  </div>
                </div>
              {/each}
              {#if accounts.length === 0}
                <div class="empty-state">No accounts configured. Add Reddit bot accounts to start the campaign.</div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- TRACKER TAB -->
        {#if activeTab === 'tracker'}
          <div class="panel">
            <div class="panel-header">
              <h2>📊 Reply Tracker</h2>
            </div>
            <div class="tracker-table">
              <table>
                <thead>
                  <tr>
                    <th>Thread</th>
                    <th>Account</th>
                    <th>Posted</th>
                    <th>Upvotes</th>
                    <th>Replies</th>
                    <th>Clicks</th>
                    <th>Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {#each trackerData as tracker}
                    <tr>
                      <td><a href={tracker.comment_url} target="_blank">{tracker.thread_title?.substring(0, 50)}...</a></td>
                      <td>{tracker.account_id}</td>
                      <td>{timeAgo(tracker.posted_at)}</td>
                      <td>{tracker.upvotes}</td>
                      <td>{tracker.replies}</td>
                      <td>{tracker.clicks}</td>
                      <td><span class="tag tag-{tracker.outcome === 'posted' ? 'posted' : 'skipped'}">{tracker.outcome}</span></td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        {/if}

        <!-- SETTINGS TAB -->
        {#if activeTab === 'settings'}
          <div class="panel">
            <h2>⚙️ Settings</h2>
            <div class="card mt-16">
              <h3>Campaign Mode</h3>
              <p class="text-muted">Auto mode posts replies automatically when they meet the threshold. Supervised mode requires approval for every post.</p>
              <div class="mt-8">
                <button class="btn {config.auto_mode ? 'btn-primary' : ''}" on:click={handleToggleAuto}>
                  {config.auto_mode ? '✅ Auto Mode ON' : '👤 Supervised Mode'}
                </button>
              </div>
            </div>

            <div class="card mt-16">
              <h3>Auto-Post Threshold</h3>
              <p class="text-muted">Minimum radar score for auto-posting. Lower = more posts, higher = more selective.</p>
              <div class="mt-8">
                <input
                  type="range"
                  min="40"
                  max="90"
                  step="5"
                  value={config.auto_threshold}
                  on:input={(e) => handleThresholdChange(Number(e.currentTarget.value))}
                />
                <div class="text-sm text-muted mt-8">Current threshold: <strong>{config.auto_threshold}</strong></div>
              </div>
            </div>

            <div class="card mt-16">
              <h3>Daily Limits</h3>
              <div class="grid-2 mt-8">
                <div>
                  <label>Max posts per account/day</label>
                  <input type="number" value={config.max_posts_per_day || 8} />
                </div>
                <div>
                  <label>Max comments per account/day</label>
                  <input type="number" value={config.max_comments_per_day || 25} />
                </div>
              </div>
            </div>

            <div class="card mt-16">
              <h3>Quick Actions</h3>
              <div class="mt-8 gap-8">
                <button class="btn" on:click={() => {
                  fetch(`${API}/api/radar/import`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify([]),
                  }).then(() => fetchData());
                }}>🔄 Force Refresh</button>
                <button class="btn" on:click={() => window.open(`${API}/api/health`, '_blank')}>🏥 Health Check</button>
              </div>
            </div>
          </div>
        {/if}
      {/if}
    </main>
  </div>
</div>

<style>
  /* ── Layout ─────────────────────────────────────────────────── */
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .logo {
    font-size: 18px;
    font-weight: 700;
    margin: 0;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 13px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .mode-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .mode-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .toggle-switch {
    position: relative;
    width: 44px;
    height: 24px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 12px;
    cursor: pointer;
    padding: 0;
  }

  .toggle-switch.toggle-on {
    background: #238636;
    border-color: #238636;
  }

  .toggle-knob {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    background: white;
    border-radius: 50%;
    transition: transform 0.2s;
  }

  .toggle-switch.toggle-on .toggle-knob {
    transform: translateX(20px);
  }

  .threshold-control {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .threshold-value {
    font-weight: 700;
    color: var(--accent);
    min-width: 24px;
    text-align: center;
  }

  .main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .sidebar {
    width: 280px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    padding: 16px;
    overflow-y: auto;
    flex-shrink: 0;
  }

  .content {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
  }

  /* ── Nav ────────────────────────────────────────────────────── */
  .nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    border-radius: 6px;
    font-size: 14px;
    text-align: left;
    width: 100%;
  }

  .nav-item.nav-active {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .nav-item:hover {
    background: var(--bg-tertiary);
  }

  .toggle-switch.toggle-on {
    background: #238636;
    border-color: #238636;
  }

  .nav-item:hover {
    background: var(--bg-tertiary);
  }

  .nav-badge {
    background: var(--accent);
    color: white;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
  }

  /* ── KPI ────────────────────────────────────────────────────── */
  .kpi-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 20px;
  }

  .kpi-card {
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    text-align: center;
  }

  .kpi-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--accent);
  }

  .kpi-label {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* ── Panel ──────────────────────────────────────────────────── */
  .panel {
    max-width: 1200px;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .panel-header h2 {
    margin: 0;
    font-size: 18px;
  }

  .filters {
    display: flex;
    gap: 8px;
  }

  .filters select, .filters input {
    width: auto;
    min-width: 140px;
  }

  /* ── Thread cards ───────────────────────────────────────────── */
  .thread-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .thread-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
  }

  .thread-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
  }

  .thread-meta {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .sub {
    color: var(--accent);
    font-size: 13px;
    font-weight: 600;
  }

  .time {
    color: var(--text-secondary);
    font-size: 12px;
  }

  .thread-score {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .score-value {
    font-weight: 700;
    font-size: 14px;
    color: var(--text-primary);
  }

  .thread-title {
    margin: 0 0 8px 0;
    font-size: 15px;
  }

  .thread-title a {
    color: var(--text-primary);
    text-decoration: none;
  }

  .thread-title a:hover {
    color: var(--accent);
  }

  .thread-body {
    color: var(--text-secondary);
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 12px;
  }

  .thread-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .thread-stat {
    color: var(--text-secondary);
    font-size: 12px;
  }

  /* ── Draft cards ────────────────────────────────────────────── */
  .draft-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .draft-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
  }

  .draft-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .draft-thread-title {
    margin: 0 0 8px 0;
    font-size: 14px;
  }

  .draft-thread-title a {
    color: var(--accent);
    text-decoration: none;
  }

  .draft-body {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 12px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    margin-bottom: 12px;
  }

  .draft-edit {
    width: 100%;
    font-family: inherit;
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
  }

  .draft-edit-actions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  .draft-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* ── Account list ───────────────────────────────────────────── */
  .account-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* ── Tracker table ──────────────────────────────────────────── */
  .tracker-table {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th, td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }

  th {
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  td a {
    color: var(--accent);
    text-decoration: none;
  }

  /* ── States ─────────────────────────────────────────────────── */
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-secondary);
  }

  .error {
    background: #da363322;
    border: 1px solid #da3633;
    border-radius: 6px;
    padding: 16px;
    color: var(--accent-red);
  }

  .empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text-secondary);
  }
</style>
