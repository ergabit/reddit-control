/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(224, 10%, 15%)',
        input: 'hsl(224, 10%, 15%)',
        ring: 'hsl(224, 70%, 50%)',
        background: 'hsl(222, 47%, 6%)',
        foreground: 'hsl(213, 31%, 91%)',
        primary: {
          DEFAULT: 'hsl(224, 70%, 50%)',
          foreground: 'hsl(210, 40%, 98%)',
        },
        secondary: {
          DEFAULT: 'hsl(222, 47%, 11%)',
          foreground: 'hsl(210, 40%, 98%)',
        },
        destructive: {
          DEFAULT: 'hsl(0, 72%, 51%)',
          foreground: 'hsl(210, 40%, 98%)',
        },
        muted: {
          DEFAULT: 'hsl(223, 47%, 14%)',
          foreground: 'hsl(215, 20%, 65%)',
        },
        accent: {
          DEFAULT: 'hsl(223, 47%, 14%)',
          foreground: 'hsl(210, 40%, 98%)',
        },
        popover: {
          DEFAULT: 'hsl(222, 47%, 8%)',
          foreground: 'hsl(210, 40%, 98%)',
        },
        card: {
          DEFAULT: 'hsl(222, 47%, 8%)',
          foreground: 'hsl(213, 31%, 91%)',
        },
      },
      borderRadius: {
        lg: '0.5rem',
        md: 'calc(0.5rem - 2px)',
        sm: 'calc(0.5rem - 4px)',
      },
    },
  },
  plugins: [],
};
