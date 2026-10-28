<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import {
    LayoutDashboard,
    Search,
    FileText,
    Users,
    BarChart3,
    Settings,
    Building2,
    ChevronDown,
  } from 'lucide-svelte';
  import { API_BASE } from '$lib/constants';

  let clients: any[] = [];
  let selectedClient: string = 'default';
  let clientMenuOpen = false;

  // Nav items
  const navItems = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/findings', label: 'Findings', icon: Search },
    { href: '/drafts', label: 'Drafts', icon: FileText },
    { href: '/accounts', label: 'Accounts', icon: Users },
    { href: '/tracker', label: 'Tracker', icon: BarChart3 },
    { href: '/settings', label: 'Settings', icon: Settings },
  ];

  // Load clients on mount
  (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/clients`);
      if (res.ok) {
        clients = await res.json();
        // Persist selected client
        const saved = localStorage.getItem('reddit-control-client');
        if (saved && clients.find((c: any) => c.id === saved)) {
          selectedClient = saved;
        }
      }
    } catch {}
  })();

  function selectClient(clientId: string) {
    selectedClient = clientId;
    localStorage.setItem('reddit-control-client', clientId);
    clientMenuOpen = false;
    // Reload current page with new client context
    location.reload();
  }

  function getClientName(id: string): string {
    const c = clients.find((cl: any) => cl.id === id);
    return c?.name || 'Unknown';
  }

  function getClientBrand(id: string): string {
    const c = clients.find((cl: any) => cl.id === id);
    return c?.brand_name || 'Reddit Control';
  }
</script>

<div class="flex h-screen overflow-hidden bg-background">
  <!-- Sidebar -->
  <aside class="w-64 border-r bg-card flex flex-col flex-shrink-0">
    <!-- Logo -->
    <div class="h-16 flex items-center px-6 border-b">
      <div class="flex items-center gap-2">
        <div class="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <span class="text-primary-foreground font-bold text-sm">RC</span>
        </div>
        <span class="font-semibold text-foreground text-sm">Reddit Control</span>
      </div>
    </div>

    <!-- Client Selector -->
    <div class="px-3 py-3 border-b">
      <div class="relative">
        <button
          class="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm bg-secondary hover:bg-secondary/80 transition-colors text-foreground"
          on:click={() => clientMenuOpen = !clientMenuOpen}
        >
          <Building2 class="h-4 w-4 text-muted-foreground" />
          <span class="flex-1 text-left truncate">{getClientName(selectedClient)}</span>
          <ChevronDown class="h-3 w-3 text-muted-foreground" />
        </button>
        {#if clientMenuOpen}
          <div class="absolute top-full left-0 right-0 mt-1 bg-card border rounded-md shadow-lg z-50 overflow-hidden">
            {#each clients as client}
              <button
                class="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground transition-colors flex items-center gap-2 {client.id === selectedClient ? 'bg-accent text-accent-foreground' : ''}"
                on:click={() => selectClient(client.id)}
              >
                {client.name}
                {#if client.id === 'default'}
                  <span class="text-xs text-muted-foreground ml-auto">(default)</span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Nav -->
    <nav class="flex-1 overflow-y-auto py-4 px-3 space-y-1">
      {#each navItems as item}
        <a
          href={item.href}
          class="flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors {($page.url.pathname === item.href || ($page.url.pathname.startsWith(item.href + '/') && item.href !== '/')) ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'}"
        >
          <svelte:component this={item.icon} class="h-4 w-4" />
          {item.label}
        </a>
      {/each}
    </nav>

    <!-- Footer -->
    <div class="border-t p-4">
      <div class="flex items-center gap-3">
        <div class="h-8 w-8 rounded-full bg-secondary flex items-center justify-center text-xs font-medium text-secondary-foreground">
          E
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-foreground truncate">Ernestas</p>
          <p class="text-xs text-muted-foreground truncate">Admin</p>
        </div>
      </div>
    </div>
  </aside>

  <!-- Main content -->
  <main class="flex-1 overflow-y-auto">
    <div class="p-6">
      <slot />
    </div>
  </main>
</div>
