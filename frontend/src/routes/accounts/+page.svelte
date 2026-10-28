<script lang="ts">
  import { onMount } from 'svelte';
  import { Users, Plus, RefreshCw, Trash2, Eye, EyeOff, Ban } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let selectedClient = localStorage.getItem('reddit-control-client') || 'default';
  let accounts: any[] = [];
  let loading = true;
  let error = '';
  let showAddAccount = false;
  let newAccount = { username: '', password: '', email: '' };

  async function fetchAccounts() {
    const res = await fetch(`${API_BASE}/api/accounts?client_id=${selectedClient}`);
    if (!res.ok) throw new Error('Failed to fetch accounts');
    return res.json();
  }

  async function handleAddAccount() {
    await fetch(`${API_BASE}/api/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newAccount),
    });
    newAccount = { username: '', password: '', email: '' };
    showAddAccount = false;
    await fetchAccounts();
  }

  async function handleToggleActive(username: string) {
    // Toggle is_active by updating the account
    const acc = accounts.find(a => a.username === username);
    if (acc) {
      await fetch(`${API_BASE}/api/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: acc.username,
          password: acc.password,
          email: acc.email,
          is_active: !acc.is_active,
        }),
      });
      await fetchAccounts();
    }
  }

  async function handleDelete(username: string) {
    if (!confirm(`Delete @${username}?`)) return;
    await fetch(`${API_BASE}/api/accounts/${username}`, { method: 'DELETE' });
    await fetchAccounts();
  }

  onMount(() => {
    fetchAccounts().then(a => { accounts = a; loading = false; }).catch(e => { error = e.message; loading = false; });
  });
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-semibold text-foreground">Bot Accounts</h1>
      <p class="text-muted-foreground mt-1">Manage Reddit bot accounts for the campaign</p>
    </div>
    <button class="btn btn-primary btn-sm" on:click={() => showAddAccount = !showAddAccount}>
      <Plus class="h-4 w-4" />
      Add Account
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
    <!-- Add Account Form -->
    {#if showAddAccount}
      <div class="card p-6">
        <h3 class="text-lg font-medium text-foreground mb-4">Add New Account</h3>
        <div class="grid gap-4 md:grid-cols-3">
          <div>
            <label class="text-sm font-medium text-foreground mb-1 block">Username</label>
            <input
              type="text"
              placeholder="reddit_username"
              bind:value={newAccount.username}
              class="input"
            />
          </div>
          <div>
            <label class="text-sm font-medium text-foreground mb-1 block">Password</label>
            <input
              type="password"
              placeholder="reddit_password"
              bind:value={newAccount.password}
              class="input"
            />
          </div>
          <div>
            <label class="text-sm font-medium text-foreground mb-1 block">Email (optional)</label>
            <input
              type="email"
              placeholder="email@example.com"
              bind:value={newAccount.email}
              class="input"
            />
          </div>
        </div>
        <div class="flex gap-2 mt-4">
          <button class="btn btn-primary btn-sm" on:click={handleAddAccount}>Add Account</button>
          <button class="btn btn-secondary btn-sm" on:click={() => showAddAccount = false}>Cancel</button>
        </div>
      </div>
    {/if}

    <!-- Account List -->
    {#if accounts.length === 0}
      <div class="card p-12 text-center">
        <Users class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 class="text-lg font-medium text-foreground">No accounts configured</h3>
        <p class="text-muted-foreground mt-2">Add Reddit bot accounts to start the campaign.</p>
      </div>
    {:else}
      <div class="space-y-4">
        {#each accounts as acc}
          <div class="card">
            <div class="p-6">
              <div class="flex items-start justify-between">
                <div>
                  <div class="flex items-center gap-2 mb-1">
                    <h3 class="text-lg font-medium text-foreground">@{acc.username}</h3>
                    {#if acc.is_active}
                      <span class="badge badge-green">Active</span>
                    {:else}
                      <span class="badge badge-secondary">Inactive</span>
                    {/if}
                  </div>
                  {#if acc.email}
                    <p class="text-sm text-muted-foreground">{acc.email}</p>
                  {/if}
                </div>
                <div class="flex items-center gap-2">
                  <button
                    class="btn btn-ghost btn-sm"
                    on:click={() => handleToggleActive(acc.username)}
                    title={acc.is_active ? 'Deactivate' : 'Activate'}
                  >
                    {#if acc.is_active}
                      <EyeOff class="h-4 w-4" />
                    {:else}
                      <Eye class="h-4 w-4" />
                    {/if}
                  </button>
                  <button
                    class="btn btn-ghost btn-sm text-destructive"
                    on:click={() => handleDelete(acc.username)}
                    title="Delete account"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                <div class="text-center p-3 bg-secondary/50 rounded-lg">
                  <p class="text-2xl font-bold text-foreground">{acc.karma || 0}</p>
                  <p class="text-xs text-muted-foreground mt-1">Karma</p>
                </div>
                <div class="text-center p-3 bg-secondary/50 rounded-lg">
                  <p class="text-2xl font-bold text-foreground">{acc.post_count_today || 0}</p>
                  <p class="text-xs text-muted-foreground mt-1">Posts Today</p>
                </div>
                <div class="text-center p-3 bg-secondary/50 rounded-lg">
                  <p class="text-2xl font-bold text-foreground">{acc.comment_count_today || 0}</p>
                  <p class="text-xs text-muted-foreground mt-1">Comments Today</p>
                </div>
                <div class="text-center p-3 bg-secondary/50 rounded-lg">
                  <p class="text-2xl font-bold text-foreground">{Math.round((acc.ban_risk || 0) * 100)}%</p>
                  <p class="text-xs text-muted-foreground mt-1">Ban Risk</p>
                </div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
