export const tokens = {
  color: {
    paper: "#fafaf8",
    ink: "#0a0a0a",
    line: "#ececea",
    cedar: "#0a7a3e",
    copper: "#d00000",
    danger: "#b91c1c",
    sidebarBg: "#ffffff",
    sidebarText: "#0a0a0a",
    sidebarActive: "rgba(208, 0, 0, 0.1)",
  },
  space: [4, 8, 12, 16, 24, 32, 48],
  radius: { input: 6, panel: 10 },
  focusRing: "2px solid #0a0a0a",
  font: {
    family: '"IBM Plex Sans Arabic", "Noto Naskh Arabic", Tahoma, sans-serif',
  },
} as const

export type Tokens = typeof tokens
