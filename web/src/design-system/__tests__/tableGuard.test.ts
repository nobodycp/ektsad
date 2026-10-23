import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative, resolve } from "node:path"

const SRC = resolve(__dirname, "../..")

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

describe("table guard", () => {
  it("has no <table in any file under src/pages", () => {
    const offenders = walk(join(SRC, "pages")).filter((f) => readFileSync(f, "utf8").includes("<table"))
    expect(offenders.map((f) => relative(SRC, f))).toEqual([])
  })

  it("keeps the only <table element in DataTable", () => {
    const offenders = walk(SRC)
      .filter((f) => /\.(tsx?|jsx?|html)$/.test(f) && !f.includes("__tests__"))
      .filter((f) => readFileSync(f, "utf8").includes("<table"))
      .map((f) => relative(SRC, f))
    expect(offenders).toEqual(["design-system/DataTable.tsx"])
  })
})
