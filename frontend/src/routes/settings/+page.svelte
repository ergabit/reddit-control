<script lang="ts">
  import { onMount } from 'svelte';
  import { Settings, RefreshCw, Zap, Shield, Clock, Building2, ExternalLink } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let selectedClient = localStorage.getItem('reddit-control-client') || 'default';
  let config: any = {};
  let loading = true;
  let error = '';
  let saving = false;

  async function fetchConfig() {
    const res = await fetch(`${API_BASE}/api/config?client_id=${selectedClient}`);
    if (!res.ok) throw new Error('Failed to fetch config');
    return res.json();
  }

  async function updateConfig(updates: any) {
    saving = true;
    try {
      await fetch(`${API_BASE}/api/config?client_id=${selectedClient}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      await fetchConfig();
    } finally {
      saving = false;
    }
  }

  async function handleToggleAuto() {
    await updateConfig({ auto_mode: !config.auto_mode });
  }

  async function handleThresholdChange(val: number) {
    await updateConfig({ auto_threshold: val });
  }

  async function handlePostsPerDayChange(val: number) {
    await updateConfig({ max_posts_per_day: val });
  }

  async function handleCommentsPerDayChange(val: number) {
    await updateConfig({ max_comments_per_day: val });
  }

  onMount(() => {
    fetchConfig().then(c => { config = c; loading = false; }).catch(e => { error = e.message; loading = false; });
  });
</script>

<div class="space-y-6">
  <div>
    <h1 class="text-2xl font-semibold text-foreground">Settings</h1>
    <p class="text-muted-foreground mt-1">Configure campaign behavior and preferences</p>
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
    <!-- Campaign Mode -->
    <div class="card">
      <div class="card-header">
        <div class="flex items-center gap-2">
          <Zap class="h-5 w-5 text-yellow-400" />
          <h2 class="card-title">Campaign Mode</h2>
        </div>
        <p class="card-description">Auto mode posts replies automatically when they meet the threshold. Supervised mode requires approval for every post.</p>
      </div>
      <div class="card-content">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium text-foreground">{config.auto_mode ? 'Auto Mode' : 'Supervised Mode'}</p>
            <p class="text-sm text-muted-foreground mt-1">{config.auto_mode ? 'Replies are posted automatically based on score threshold' : 'Every reply requires manual approval before posting'}</p>
          </div>
          <button
            class="btn {config.auto_mode ? 'btn-primary' : 'btn-secondary'}"
            on:click={handleToggleAuto}
          >
            {config.auto_mode ? 'Auto Mode ON' : 'Switch to Auto'}
          </button>
        </div>
      </div>
    </div>

    <!-- Auto-Post Threshold -->
    <div class="card">
      <div class="card-header">
        <div class="flex items-center gap-2">
          <Shield class="h-5 w-5 text-blue-400" />
          <h2 class="card-title">Auto-Post Threshold</h2>
        </div>
        <p class="card-description">Minimum radar score for auto-posting. Lower = more posts, higher = more selective.</p>
      </div>
      <div class="card-content">
        <div class="space-y-4">
          <input
            type="range"
            min="40"
            max="90"
            step="5"
            value={config.auto_threshold}
            on:input={(e) => handleThresholdChange(Number(e.currentTarget.value))}
            class="w-full"
          />
          <div class="flex items-center justify-between text-sm">
            <span class="text-muted-foreground">40 (Aggressive)</span>
            <span class="font-medium text-foreground">{config.auto_threshold}</span>
            <span class="text-muted-foreground">90 (Conservative)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Daily Limits -->
    <div class="card">
      <div class="card-header">
        <div class="flex items-center gap-2">
          <Clock class="h-5 w-5 text-emerald-400" />
          <h2 class="card-title">Daily Limits</h2>
        </div>
        <p class="card-description">Maximum posts and comments per account per day to minimize ban risk.</p>
      </div>
      <div class="card-content">
        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <label class="text-sm font-medium text-foreground mb-2 block">Max posts per account/day</label>
            <input
              type="number"
              bind:value={config.max_posts_per_day}
              on:change={(e) => handlePostsPerDayChange(Number(e.currentTarget.value))}
              class="input"
            />
          </div>
          <div>
            <label class="text-sm font-medium text-foreground mb-2 block">Max comments per account/day</label>
            <input
              type="number"
              bind:value={config.max_comments_per_day}
              on:change={(e) => handleCommentsPerDayChange(Number(e.currentTarget.value))}
              class="input"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- System Info -->
    <div class="card">
      <div class="card-header">
        <div class="flex items-center gap-2">
          <RefreshCw class="h-5 w-5 text-purple-400" />
          <h2 class="card-title">System</h2>
        </div>
      </div>
      <div class="card-content">
        <div class="space-y-3">
          <div class="flex items-center justify-between text-sm">
            <span class="text-muted-foreground">Dashboard URL</span>
            <span class="text-foreground font-mono">http://192.168.0.38:3900</span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-muted-foreground">API URL</span>
            <span class="text-foreground font-mono">http://192.168.0.38:8900</span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-muted-foreground">MCP Endpoint</span>
            <span class="text-foreground font-mono">POST /api/mcp/call</span>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-muted-foreground">Last Updated</span>
            <span class="text-foreground">{new Date().toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Client Management -->
    <div class="card">
      <div class="card-header">
        <div class="flex items-center gap-2">
          <Building2 class="h-5 w-5 text-blue-400" />
          <h2 class="card-title">Client Management</h2>
        </div>
        <p class="card-description">Manage multiple clients, each with their own radar, accounts, and settings.</p>
      </div>
      <div class="card-content">
        <div class="flex items-center gap-3">
          <span class="text-sm text-muted-foreground">Current client:</span>
          <span class="text-sm font-medium text-foreground">{selectedClient}</span>
        </div>
        <div class="mt-4">
          <a href="https://github.com/ergabit/isf-reddit-control" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
            <ExternalLink class="h-3 w-3" />
            View API Docs
          </a>
        </div>
      </div>
    </div>
  {/if}
</div>
