<script>
  import { page } from '$app/stores';
  import {
    LayoutDashboard,
    Search,
    FileText,
    Users,
    BarChart3,
    Settings,
  } from 'lucide-svelte';

  const navItems = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/findings', label: 'Findings', icon: Search },
    { href: '/drafts', label: 'Drafts', icon: FileText },
    { href: '/accounts', label: 'Accounts', icon: Users },
    { href: '/tracker', label: 'Tracker', icon: BarChart3 },
    { href: '/settings', label: 'Settings', icon: Settings },
  ];
</script>

<div class="flex h-screen overflow-hidden bg-background">
  <!-- Sidebar -->
  <aside class="w-64 border-r bg-card flex flex-col">
    <!-- Logo -->
    <div class="h-16 flex items-center px-6 border-b">
      <div class="flex items-center gap-2">
        <div class="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <span class="text-primary-foreground font-bold text-sm">iS</span>
        </div>
        <span class="font-semibold text-foreground">Reddit Control</span>
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
