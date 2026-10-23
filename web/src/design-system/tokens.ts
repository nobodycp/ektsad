export const tokens = {
  color: {
    paper: "#f3efe6",
    ink: "#1a1814",
    line: "#e2d9cc",
    cedar: "#1e4a38",
    copper: "#9a4e2a",
    danger: "#8c2f2a",
    sidebarBg: "#1a1814",
    sidebarText: "#f3efe6",
    sidebarActive: "#1e4a38",
  },
  space: [4, 8, 12, 16, 24, 32, 48],
  radius: { input: 6, panel: 10 },
  focusRing: "2px solid #1e4a38",
  font: {
    family: '"IBM Plex Sans Arabic", "Noto Naskh Arabic", Tahoma, sans-serif',
  },
} as const

export type Tokens = typeof tokens
