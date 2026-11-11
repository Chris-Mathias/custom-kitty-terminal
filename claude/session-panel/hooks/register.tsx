import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, ImageProps, Register, RenderChildren } from 'claude-code'

import type { FileTouch, GitInfo, PastedImage, SessionRow, Todo, TodoStatus, TouchKind, Worktree } from '../types'

const PANE = 'session-panel'
// Requested width for the side pane (whatever you drag with the mouse wins).
const PANE_COLUMNS = 30
// Transparent background: the panel uses the terminal's background color.
const open = (S: Strings) =>
  ({ id: PANE, title: S['panel.title'], columns: PANE_COLUMNS, backgroundColor: 'transparent' }) as const

// ---------- language ----------
// Built-in English text; the user's language comes from the settings menu (ct config):
// ~/.config/custom-kitty-terminal/settings.json picks the language and the repo's
// i18n/<lang>.json has the text (the repo is found through this plugin folder's real path).
const EN = {
  'panel.title': 'Session',
  'panel.sessions': 'SESSIONS',
  'panel.git': 'GIT',
  'panel.tasks': 'TASKS',
  'panel.files': 'FILES',
  'panel.agents': 'SUBAGENTS',
  'panel.no_agents': 'none running',
  'panel.main_conversation': 'main conversation',
  'panel.agent_command_description': "Shows a subagent's conversation: /agent 2, next, prev or main",
  'panel.no_such_agent': 'No subagent with that number.',
  'panel.reading': 'reading…',
  'panel.none_open': 'none open',
  'panel.not_a_repo': 'not in a repository',
  'panel.nothing_changed': 'nothing changed',
  'panel.file': 'file',
  'panel.files_count': 'files',
  'panel.none': 'none',
  'panel.none_yet': 'none yet',
  'panel.more_tasks': 'tasks',
  'panel.detached_head': 'detached HEAD',
  'panel.kitty_switch_failed': "couldn't switch tabs",
  'panel.command_description': 'Opens the session panel (sessions, git, tasks, files)',
  'panel.opened': 'Session panel opened.',
  'panel.mark_read': 'R',
  'panel.mark_edited': 'E',
  'panel.mark_created': 'N',
  'panel.images': 'IMAGES',
  'panel.no_images': 'none pasted',
}
type Strings = typeof EN

async function readJson($: Engine, path: string): Promise<Record<string, unknown>> {
  try {
    const value = JSON.parse(String(await $.fs.read(path)))
    return value && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}

// ---------- layout ----------
// Which sections show, in what order, and whether the panel opens by itself
// (settings menu → Claude Code → Side panel).
const SECTIONS = ['sessions', 'agents', 'tasks', 'git', 'files', 'images'] as const
// Sections that existed before settings.json recorded "known" (lib/ckt.py does the same):
// a section added later shows up for people who already had a saved order.
const SECTIONS_V1: readonly string[] = ['sessions', 'agents', 'tasks', 'git', 'files']
type Section = (typeof SECTIONS)[number]
type Layout = { sections: Section[]; autoOpen: boolean; closeButtons: boolean; confirmClose: string }
const DEFAULT_LAYOUT: Layout = { sections: [...SECTIONS], autoOpen: true, closeButtons: false, confirmClose: 'running' }

async function readSettings($: Engine): Promise<Record<string, unknown>> {
  const dir = (await $.env.get('CKT_CONFIG_DIR')) || `${await $.env.get('HOME')}/.config/custom-kitty-terminal`
  return readJson($, `${dir}/settings.json`)
}

function layoutOf(settings: Record<string, unknown>): Layout {
  const panel = (settings.panel ?? {}) as { sections?: unknown; auto_open?: unknown; known?: unknown }
  const sections = Array.isArray(panel.sections)
    ? (panel.sections as unknown[]).filter(
        (x, i, all): x is Section => SECTIONS.includes(x as Section) && all.indexOf(x) === i,
      )
    : [...SECTIONS]
  const known = Array.isArray(panel.known) ? (panel.known as unknown[]) : SECTIONS_V1
  for (const name of SECTIONS) if (!known.includes(name) && !sections.includes(name)) sections.push(name)
  return {
    sections,
    autoOpen: typeof panel.auto_open === 'boolean' ? panel.auto_open : true,
    closeButtons: settings.panel_close_buttons === true,
    confirmClose: typeof settings.confirm_close === 'string' ? settings.confirm_close : 'running',
  }
}

async function loadStrings($: Engine): Promise<Strings> {
  try {
    const settings = await readSettings($)
    await update($, layout, () => layoutOf(settings))
    const lang = settings.language === 'pt' || settings.language === 'zh' ? settings.language : 'en'
    const real = (await $.fs.stat($.plugin.root, { resolve: true })).realPath
    if (!real) return EN
    const repo = real.split('/').slice(0, -2).join('/')
    const pick = (o: Record<string, unknown>) =>
      Object.fromEntries(Object.entries(o).filter(([k, v]) => k in EN && typeof v === 'string'))
    const en = pick(await readJson($, `${repo}/i18n/en.json`))
    const own = lang === 'en' ? {} : pick(await readJson($, `${repo}/i18n/${lang}.json`))
    return { ...EN, ...en, ...own }
  } catch {
    return EN
  }
}

async function refreshStrings($: Engine): Promise<Strings> {
  const next = await loadStrings($)
  await update($, strings, () => next)
  return next
}

const textOf = async ($: Engine): Promise<Strings> => ({ ...EN, ...(await read($, strings)) })

const todos = atom({ plugin: 'session-panel', key: 'todos' } as const, [] as Todo[], { shape: 'todos-1' })
const files = atom({ plugin: 'session-panel', key: 'files' } as const, [] as FileTouch[], { shape: 'files-3' })
const images = atom({ plugin: 'session-panel', key: 'images' } as const, [] as PastedImage[], { shape: 'images-1' })
const git = atom({ plugin: 'session-panel', key: 'git' } as const, null as GitInfo | null, { shape: 'git-3' })
const sessions = atom({ plugin: 'session-panel', key: 'sessions' } as const, null as SessionRow[] | null, {
  shape: 'sessions-4',
})
const strings = atom({ plugin: 'session-panel', key: 'strings' } as const, {} as Record<string, string>, {
  shape: 'strings-1',
})
const layout = atom({ plugin: 'session-panel', key: 'layout' } as const, null as Layout | null, { shape: 'layout-2' })
// Branch name stored for a detached HEAD; drawn in the user's language.
const DETACHED = '\u0000detached'

// Tools that may change the repository: git is re-read after them.
const MUTATING = new Set(['Bash', 'Edit', 'Write', 'NotebookEdit', 'MultiEdit'])
const KIND_RANK: Record<TouchKind, number> = { read: 0, edited: 1, created: 2 }

// ---------- git ----------
async function readGit($: Engine): Promise<GitInfo> {
  const empty: GitInfo = { isRepo: false, branch: '', ahead: 0, behind: 0, files: [], added: 0, removed: 0, worktrees: [] }
  const st = await $.process.run(['git', '--no-optional-locks', 'status', '--porcelain=v1', '-b'], { timeoutMs: 5000 })
  if (st.exitCode !== 0) return empty

  const lines = st.stdout.split('\n').filter(Boolean)
  const head = lines[0]?.startsWith('## ') ? lines.shift()!.slice(3) : ''
  let branch = (head.split('...')[0] ?? '').replace(/^No commits yet on /, '')
  if (branch.startsWith('HEAD')) branch = DETACHED
  const ahead = Number(/ahead (\d+)/.exec(head)?.[1] ?? 0)
  const behind = Number(/behind (\d+)/.exec(head)?.[1] ?? 0)
  const changed = lines.map(l => ({ status: l.slice(0, 2).trim() || '?', path: l.slice(3) }))

  let added = 0
  let removed = 0
  const diff = await $.process.run(['git', '--no-optional-locks', 'diff', '--numstat', 'HEAD'], { timeoutMs: 5000 })
  if (diff.exitCode === 0) {
    for (const row of diff.stdout.split('\n')) {
      const [a, r] = row.split('\t')
      if (/^\d+$/.test(a ?? '')) added += Number(a)
      if (/^\d+$/.test(r ?? '')) removed += Number(r)
    }
  }
  const top = await $.process.run(['git', 'rev-parse', '--show-toplevel'], { timeoutMs: 5000 })
  const root = top.exitCode === 0 ? top.stdout.trim() : undefined
  return { isRepo: true, branch, ahead, behind, files: changed, added, removed, worktrees: await readWorktrees($), root }
}

// Worktrees other than the main one (e.g. the subagents' in .claude/worktrees/)
const shortAgent = (s: string) => s.replace(/(agent-[0-9a-f]{6})[0-9a-f]+/, '$1')
async function readWorktrees($: Engine): Promise<Worktree[]> {
  const top = await $.process.run(['git', 'rev-parse', '--show-toplevel'], { timeoutMs: 5000 })
  const list = await $.process.run(['git', 'worktree', 'list', '--porcelain'], { timeoutMs: 5000 })
  if (top.exitCode !== 0 || list.exitCode !== 0) return []
  const main = top.stdout.trim()
  const found: { path: string; branch: string }[] = []
  for (const block of list.stdout.split('\n\n')) {
    const path = /^worktree (.+)$/m.exec(block)?.[1]
    if (!path || path === main) continue
    const branch = /^branch refs\/heads\/(.+)$/m.exec(block)?.[1] ?? DETACHED
    found.push({ path, branch })
  }
  return Promise.all(
    found.slice(0, 6).map(async wt => {
      const st = await $.process.run(['git', '--no-optional-locks', '-C', wt.path, 'status', '--porcelain'], {
        timeoutMs: 5000,
      })
      return {
        name: shortAgent(wt.path.split('/').pop() ?? wt.path),
        branch: shortAgent(wt.branch),
        changes: st.exitCode === 0 ? st.stdout.split('\n').filter(Boolean).length : 0,
      }
    }),
  )
}

async function refreshGit($: Engine) {
  try {
    const info = await readGit($)
    await update($, git, () => info)
  } catch {
    // git missing or slow: keep the last value
  }
}

// ---------- open sessions (claude agents --json) ----------
// Title Claude gives each session (the same as the terminal tab's).
// Read from the end of the transcript; internal format, hence the name as a fallback.
const titles = new Map<string, { title: string; at: number }>()
async function sessionTitles($: Engine, ids: string[]): Promise<Map<string, string>> {
  const now = Date.now()
  const stale = ids.filter(id => (titles.get(id)?.at ?? 0) < now - 60000)
  if (stale.length) {
    const script =
      'for id in "$@"; do f=$(ls "$HOME"/.claude/projects/*/"$id".jsonl 2>/dev/null | head -1); ' +
      '[ -n "$f" ] || continue; ' +
      't=$(grep -oE \'"(customTitle|aiTitle)":"[^"]*"\' "$f" | tail -1 | sed \'s/^"[a-zA-Z]*":"//; s/"$//\'); ' +
      'printf "%s\\t%s\\n" "$id" "$t"; done'
    const run = await $.process.run(['sh', '-c', script, 'titles', ...stale], { timeoutMs: 10000 })
    for (const id of stale) titles.set(id, { title: titles.get(id)?.title ?? '', at: now })
    for (const line of run.stdout.split('\n')) {
      const [id, title] = line.split('\t')
      if (id && title) titles.set(id, { title, at: now })
    }
  }
  return new Map(ids.map(id => [id, titles.get(id)?.title ?? '']))
}

// Which tmux pane each session runs in: walks up claude's parent processes
// until it finds a tmux pane's process (list-panes -a).
const PANES_SCRIPT = String.raw`panes=$(tmux list-panes -a -F "#{pane_pid} #{pane_id}" 2>/dev/null) || exit 0; for p in "$@"; do q=$p; while [ -n "$q" ] && [ "$q" -gt 1 ]; do m=$(printf "%s\n" "$panes" | awk -v q="$q" "\$1==q{print \$2}"); if [ -n "$m" ]; then printf "%s\t%s\n" "$p" "$m"; break; fi; q=$(awk "{print \$4}" /proc/$q/stat 2>/dev/null); done; done; true`

async function tmuxPanes($: Engine, pids: number[]): Promise<Map<number, string>> {
  const run = await $.process.run(['sh', '-c', PANES_SCRIPT, 'panes', ...pids.map(String)], { timeoutMs: 5000 })
  const out = new Map<number, string>()
  for (const line of run.stdout.split('\n')) {
    const [pid, pane] = line.split('\t')
    if (pid && pane) out.set(Number(pid), pane)
  }
  return out
}

// Which kitty window each session runs in: kitty puts KITTY_WINDOW_ID and
// KITTY_LISTEN_ON in the shell's environment, and claude inherits both.
const KITTY_SCRIPT = String.raw`for p in "$@"; do e=$(tr "\0" "\n" < /proc/$p/environ 2>/dev/null); w=$(printf "%s\n" "$e" | sed -n "s/^KITTY_WINDOW_ID=//p"); s=$(printf "%s\n" "$e" | sed -n "s/^KITTY_LISTEN_ON=//p"); [ -n "$w" ] && [ -n "$s" ] && printf "%s\t%s\t%s\n" "$p" "$w" "$s"; done; true`

async function kittyWindows($: Engine, pids: number[]): Promise<Map<number, { window: string; socket: string }>> {
  const run = await $.process.run(['sh', '-c', KITTY_SCRIPT, 'kitty', ...pids.map(String)], { timeoutMs: 5000 })
  const out = new Map<number, { window: string; socket: string }>()
  for (const line of run.stdout.split('\n')) {
    const [pid, window, socket] = line.split('\t')
    if (pid && window && socket) out.set(Number(pid), { window, socket })
  }
  return out
}

// Which kitty tab each window is in (number and title, as the tab bar shows
// them), so sessions that share a tab are drawn together.
type TabInfo = { key: string; label: string; order: number }
async function kittyTabs($: Engine, sockets: string[]): Promise<Map<string, TabInfo>> {
  const out = new Map<string, TabInfo>()
  let order = 0
  for (const socket of sockets) {
    try {
      const run = await $.process.run(['kitten', '@', '--to', socket, 'ls'], { timeoutMs: 5000 })
      if (run.exitCode !== 0) continue
      type Ls = { tabs?: { id: number; title?: string; windows?: { id: number }[] }[] }[]
      for (const osWindow of JSON.parse(run.stdout) as Ls) {
        ;(osWindow.tabs ?? []).forEach((tab, i) => {
          const title = (tab.title ?? '').replace(/^[✳◐⠂⠐·*\s]+/, '').trim()
          const info = { key: `${socket}#${tab.id}`, label: `${i + 1} ${title}`.trim(), order: order++ }
          for (const w of tab.windows ?? []) out.set(`${socket}#${w.id}`, info)
        })
      }
    } catch {
      // kitty gone or busy: no grouping this time
    }
  }
  return out
}

// The x of a session (settings: "Close button on panel sessions"): closes its
// kitty window, asking first in that tab with the same box as Ctrl+Alt+W.
async function closeSession($: Engine, row: SessionRow) {
  const k = row.kitty
  if (!k) return
  const { confirmClose } = (await read($, layout)) ?? DEFAULT_LAYOUT
  const argv =
    confirmClose === 'never'
      ? ['kitten', '@', '--to', k.socket, 'close-window', '--match', `id:${k.window}`]
      : [
          'kitten', '@', '--to', k.socket, 'launch', '--type=overlay', '--match', `id:${k.window}`,
          `${await $.env.get('HOME')}/.config/kitty/close-tab-dialog.sh`, `window:${k.window}`, `Claude Code · ${row.title}`,
        ]
  const run = await $.process.run(argv, { timeoutMs: 5000 })
  if (run.exitCode !== 0) $.ui.toast(`kitty: ${run.stderr.trim()}`)
}

async function focusKitty($: Engine, k: { window: string; socket: string }) {
  const run = await $.process.run(['kitten', '@', '--to', k.socket, 'focus-window', '--match', `id:${k.window}`], {
    timeoutMs: 5000,
  })
  if (run.exitCode !== 0) $.ui.toast(`kitty: ${run.stderr.trim() || (await textOf($))['panel.kitty_switch_failed']}`)
}

// Click on a session: switch to it and then reopen the panel, so the
// focus ring doesn't stay on the clicked row (the white square).
async function pressSession($: Engine, kitty?: { window: string; socket: string }, pane?: string) {
  if (kitty) await focusKitty($, kitty)
  else if (pane) await switchTo($, pane)
  await $.ui.close({ id: PANE })
  await $.ui.open(open(await textOf($)))
}

// Switches tmux to the chosen session's window/pane.
async function switchTo($: Engine, pane: string) {
  const sw = await $.process.run(['tmux', 'switch-client', '-t', pane], { timeoutMs: 5000 })
  await $.process.run(['tmux', 'select-window', '-t', pane], { timeoutMs: 5000 })
  await $.process.run(['tmux', 'select-pane', '-t', pane], { timeoutMs: 5000 })
  if (sw.exitCode !== 0 && !/no current client/i.test(sw.stderr)) $.ui.toast(`tmux: ${sw.stderr.trim()}`)
}

type AgentJson = { pid?: number; sessionId?: string; name?: string; cwd?: string; status?: string; kind?: string; startedAt?: number }

async function refreshSessions($: Engine) {
  try {
    const [run, self] = await Promise.all([
      $.process.run(['claude', 'agents', '--json'], { timeoutMs: 15000 }),
      $.session.id(),
    ])
    if (run.exitCode !== 0) return
    const raw = (JSON.parse(run.stdout) as AgentJson[]).filter(s => s.sessionId)
    const pids = raw.map(s => s.pid ?? 0).filter(Boolean)
    const [named, panes, kittys] = await Promise.all([
      sessionTitles($, raw.map(s => s.sessionId!)),
      tmuxPanes($, pids),
      kittyWindows($, pids),
    ])
    const tabs = await kittyTabs($, [...new Set([...kittys.values()].map(k => k.socket))])
    const list = raw
      .sort((a, b) => (a.startedAt ?? 0) - (b.startedAt ?? 0))
      .map(
        (s): SessionRow => ({
          id: s.sessionId!,
          name: s.name ?? s.sessionId!.slice(0, 8),
          title: named.get(s.sessionId!) || s.name || s.sessionId!.slice(0, 8),
          folder: (s.cwd ?? '').split('/').filter(Boolean).pop() ?? '',
          status: s.status ?? '',
          isBackground: s.kind === 'background',
          isSelf: s.sessionId === self,
          tmuxPane: s.pid ? panes.get(s.pid) : undefined,
          kitty: s.pid ? kittys.get(s.pid) : undefined,
          tab: s.pid && kittys.get(s.pid) ? tabs.get(`${kittys.get(s.pid)!.socket}#${kittys.get(s.pid)!.window}`) : undefined,
        }),
      )
    await update($, sessions, () => list)
  } catch {
    // claude not on PATH or unexpected output: keep the last value
  }
}

// Sessions grouped by kitty tab, in tab order; the ones outside kitty come last.
function groupByTab(rows: SessionRow[]): { key: string; label: string; rows: SessionRow[] }[] {
  const groups = new Map<string, { key: string; label: string; order: number; rows: SessionRow[] }>()
  for (const row of rows) {
    const key = row.tab?.key ?? ''
    const g = groups.get(key) ?? { key, label: row.tab?.label ?? '', order: row.tab?.order ?? 1e9, rows: [] }
    g.rows.push(row)
    groups.set(key, g)
  }
  return [...groups.values()].sort((a, b) => a.order - b.order)
}

// ---------- subagents ----------
// The session's subagents come from $.agent.list(); claude/subagent-statusline.sh
// also saves what each one is doing right now (a file that stopped changing
// means the list below the prompt is gone). Pressing a row, its digit (with the
// panel focused) or /agent shows that subagent's conversation.
type AgentRow = { id: string; name?: string; label?: string; status?: string; canView?: boolean }
const AGENTS_STALE_MS = 20000
const agents = atom({ plugin: 'session-panel', key: 'agents' } as const, [] as AgentRow[], { shape: 'agents-2' })
// The conversation in view, as the last drawing of the panel saw it.
let viewedAgent: string | undefined

async function savedRows($: Engine): Promise<AgentRow[]> {
  try {
    const [home, id] = await Promise.all([$.env.get('HOME'), $.session.id()])
    const path = `${home}/.cache/custom-kitty-terminal/agents/${id}.json`
    const stat = await $.fs.stat(path)
    if (Date.now() - stat.mtimeMs > AGENTS_STALE_MS) return []
    const rows = JSON.parse(String(await $.fs.read(path)))
    return Array.isArray(rows) ? (rows as AgentRow[]) : []
  } catch {
    return []
  }
}

async function refreshAgents($: Engine): Promise<AgentRow[]> {
  const saved = await savedRows($)
  let listed: AgentRow[] = []
  try {
    const now = new Map(saved.map(r => [r.id, r.label]))
    listed = (await $.agent.list())
      .filter(a => !a.parentId)
      .map(a => ({
        id: a.id,
        name: a.type,
        label: now.get(a.id) || a.description,
        status: a.status,
        canView: true,
      }))
  } catch {
    // no agent list here: show what the status line saved
  }
  const rows = listed.length ? listed : saved
  await update($, agents, () => rows)
  return rows
}

async function showAgent($: Engine, agentId?: string) {
  const r = await $.ui.view(agentId ? { agentId } : {})
  const why = (r as { deny?: string } | undefined)?.deny
  if (why) $.ui.toast(why)
}

// ---------- files and tasks ----------
async function touch($: Engine, rawPath: string, kind: TouchKind) {
  const cwd = await $.session.cwd()
  const abs = rawPath.startsWith('/') ? rawPath : `${cwd}/${rawPath}`
  const path = abs.startsWith(cwd + '/') ? abs.slice(cwd.length + 1) : abs
  await update($, files, list => {
    const old = list.find(f => f.path === path)
    const best = old && KIND_RANK[old.kind] > KIND_RANK[kind] ? old.kind : kind
    return [{ path, abs, kind: best, at: Date.now() }, ...list.filter(f => f.path !== path)].slice(0, 60)
  })
}

// Clicking a file in the panel opens it in your editor (ckt-open: ct config → Behavior → Editor;
// images go to the image viewer). The panel can't tell a Ctrl+click from a click, so any click opens.
async function openFile($: Engine, abs: string) {
  const run = await $.process.run(['sh', '-c', 'exec "$HOME/.local/bin/ckt-open" "$1"', 'ckt-open', abs], {
    timeoutMs: 10000,
  })
  if (run.exitCode !== 0) $.ui.toast(run.stderr.trim() || `ckt-open: ${abs}`)
}

// ---------- pasted images ----------
// Each image pasted into this session is saved (as Claude got it) to
// ~/.cache/custom-kitty-terminal/images/<session>/<n>.<ext>, n being its [Image #n]:
// the panel shows the PNGs as thumbnails, kitty's Ctrl+click on [Image #n] opens it,
// and a resumed session finds its images again. Folders older than two weeks are removed.
const IMAGE_EXT: Record<string, string> = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp' }

async function imageDir($: Engine): Promise<string | undefined> {
  const home = await $.env.get('HOME')
  const id = (await $.session.id()).replace(/[^A-Za-z0-9_-]/g, '')
  return home && id ? `${home}/.cache/custom-kitty-terminal/images/${id}` : undefined
}

// Width and height from a PNG's header (bytes 16-23 of the IHDR chunk).
function pngSize(base64: string): { width: number; height: number } | undefined {
  try {
    const head = atob(base64.slice(0, 44))
    if (head.slice(1, 4) !== 'PNG') return undefined
    const num = (at: number) =>
      ((head.charCodeAt(at) << 24) | (head.charCodeAt(at + 1) << 16) | (head.charCodeAt(at + 2) << 8) | head.charCodeAt(at + 3)) >>> 0
    return { width: num(16), height: num(20) }
  } catch {
    return undefined
  }
}

async function saveImage($: Engine, id: string, n: number): Promise<PastedImage | undefined> {
  const dir = await imageDir($)
  if (!dir) return undefined
  let base64 = ''
  let mediaType = ''
  let offset: number | undefined = 0
  while (offset !== undefined) {
    const part = await $.prompt.media(offset ? ({ id, offset } as { id: string }) : { id })
    if (!('base64' in part) || typeof part.base64 !== 'string') return undefined
    base64 += part.base64
    mediaType = part.mediaType
    offset = part.next
  }
  const ext = IMAGE_EXT[mediaType] ?? 'img'
  const file = `${dir}/${n}.${ext}`
  const run = await $.process.run(['sh', '-c', 'mkdir -p "$(dirname "$1")" && base64 -d > "$1"', 'save', file], {
    stdin: base64,
    timeoutMs: 15000,
  })
  if (run.exitCode !== 0) return undefined
  return { n, file, isPng: ext === 'png', ...pngSize(base64) }
}

// The images saved by this session earlier (a resumed session, or a reload).
async function loadSavedImages($: Engine) {
  const dir = await imageDir($)
  if (!dir) return
  try {
    const entries = await $.fs.list(dir)
    const found: PastedImage[] = []
    for (const e of entries) {
      const m = /^(\d+)\.(\w+)$/.exec(e.name)
      if (!m) continue
      const file = `${dir}/${e.name}`
      let size: { width: number; height: number } | undefined
      if (m[2] === 'png') {
        const { base64 } = (await $.fs.read(file, { as: 'bytes' })) as unknown as { base64: string }
        size = pngSize(base64.slice(0, 44))
      }
      found.push({ n: Number(m[1]), file, isPng: m[2] === 'png', ...size })
    }
    if (found.length) await update($, images, () => found.sort((a, b) => a.n - b.n))
  } catch {
    // nothing saved yet
  }
  void $.process.run(['sh', '-c', 'find "$1" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +', 'clean',
    dir.split('/').slice(0, -1).join('/')], { timeoutMs: 10000 }).catch(() => {})
}

// ---------- drawing ----------
// East Asian wide characters (CJK, Hangul, full-width forms, most emoji) take two columns.
const WIDE: [number, number][] = [
  [0x1100, 0x115f], [0x2e80, 0x303e], [0x3041, 0x33ff], [0x3400, 0x4dbf], [0x4e00, 0x9fff],
  [0xa000, 0xa4cf], [0xac00, 0xd7a3], [0xf900, 0xfaff], [0xfe30, 0xfe4f], [0xff00, 0xff60],
  [0xffe0, 0xffe6], [0x1f300, 0x1f64f], [0x1f900, 0x1f9ff], [0x20000, 0x3fffd],
]
const charCells = (ch: string) => {
  const c = ch.codePointAt(0) ?? 0
  return WIDE.some(([a, b]) => c >= a && c <= b) ? 2 : 1
}
// Screen columns of a string.
const cells = (s: string) => {
  let n = 0
  for (const ch of s) n += charCells(ch)
  return n
}

// Truncates at the end, for text (tasks, names).
const fitHead = (s: string, n: number) => {
  if (cells(s) <= n) return s
  let out = ''
  let w = 0
  for (const ch of s) {
    const cw = charCells(ch)
    if (w + cw > Math.max(1, n - 1)) break
    out += ch
    w += cw
  }
  return (out || [...s][0]) + '…'
}

// File name and, if it fits, its folder (drawn dimmed): "register.tsx hooks"
const fileLabel = (path: string, n: number): { base: string; dir?: string } => {
  const parts = path.split('/')
  const base = parts.pop() ?? path
  const dir = parts.pop()
  if (cells(base) >= n) return { base: fitHead(base, n) }
  return dir && cells(base) + 1 + cells(dir) <= n ? { base, dir } : { base }
}

const TODO_MARK: Record<TodoStatus, string> = { completed: '✓', in_progress: '◐', pending: '○' }
const TODO_COLOR: Record<TodoStatus, string> = { completed: 'success', in_progress: 'permission', pending: 'inactive' }
const TOUCH_COLOR: Record<TouchKind, string> = { read: 'inactive', edited: 'warning', created: 'success' }
const GIT_COLOR = (s: string) => (s === '??' || s.includes('A') ? 'success' : s.includes('D') ? 'error' : 'warning')
const SESSION_LOOK = (status: string): { mark: string; color: string } =>
  status === 'busy'
    ? { mark: '◐', color: 'permission' }
    : status === 'idle'
      ? { mark: '○', color: 'inactive' }
      : { mark: '●', color: 'warning' } // waiting for you or another state

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const S = await refreshStrings($)
    await $.command.register({ name: 'panel', description: S['panel.command_description'] })
    await $.command.register({
      name: 'agent',
      description: S['panel.agent_command_description'],
      argumentHint: '[n|next|prev|main]',
      immediate: true,
    })
    if (((await read($, layout)) ?? DEFAULT_LAYOUT).autoOpen) void $.ui.open(open(S))
    // The language can change from the settings menu while the session runs.
    $.clock.every(5000, () => void refreshStrings($))

    void refreshGit($)
    void refreshSessions($)
    void loadSavedImages($)
    $.clock.every(15000, () => void refreshGit($))
    // Sessions: the state (busy/idle) is re-read every 4 s; opening or
    // closing a session is noticed in ~1 s by watching the folder where Claude Code
    // records each open session (~/.claude/sessions, one file per process).
    void refreshAgents($)
    $.clock.every(2000, () => void refreshAgents($))
    $.clock.every(4000, () => void refreshSessions($))
    const home = await $.env.get('HOME')
    if (home) {
      let last = ''
      $.clock.every(1000, () => {
        void $.fs
          .list(`${home}/.claude/sessions`)
          .then(entries => {
            const now = entries
              .map(x => x.name)
              .filter(n => n.endsWith('.json'))
              .sort()
              .join(',')
            if (now !== last) {
              const changed = last !== ''
              last = now
              if (changed) void refreshSessions($)
            }
          })
          .catch(() => {})
      })
    }

    return next(e)
  })

  on('command.run', { command: 'panel' }, async $ => {
    const S = await refreshStrings($)
    await $.ui.open(open(S))
    void refreshGit($)
    void refreshSessions($)
    return { text: S['panel.opened'] }
  })

  on('command.run', { command: 'agent' }, async ($, e) => {
    const rows = (await refreshAgents($)).filter(r => r.canView)
    const arg = e.args.trim().toLowerCase()
    const at = rows.findIndex(r => r.id === viewedAgent)
    let target: AgentRow | undefined
    if (arg === 'main' || arg === '0') target = undefined
    else if (arg === '' || arg === 'next') target = rows[(at + 1) % Math.max(1, rows.length)]
    else if (arg === 'prev') target = rows[at <= 0 ? rows.length - 1 : at - 1]
    else target = rows[Number(arg) - 1]
    if (arg !== 'main' && arg !== '0' && !target) return { text: (await textOf($))['panel.no_such_agent'] }
    await showAgent($, target?.id)
    viewedAgent = target?.id
    return {}
  })

  on('prompt.submit', async ($, e, next) => {
    try {
      const pasted = (e.attachments ?? []).filter(a => a.type === 'image' && a.id)
      if (pasted.length) {
        // The text names them in order: "[Image #3]"; without it, number after the last one.
        const named = [...e.text.matchAll(/\[Image #(\d+)\]/g)].map(m => Number(m[1]))
        const known = await read($, images)
        let last = Math.max(0, ...known.map(i => i.n))
        const saved: PastedImage[] = []
        for (const [i, a] of pasted.entries()) {
          const n = named[i] ?? ++last
          last = Math.max(last, n)
          const img = await saveImage($, a.id!, n)
          if (img) saved.push(img)
        }
        if (saved.length)
          await update($, images, list =>
            [...list.filter(i => !saved.some(x => x.n === i.n)), ...saved].sort((a, b) => a.n - b.n),
          )
      }
    } catch {
      // the panel never gets in the way of a prompt
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (ran.deny !== undefined || ran.isError === true) return ran

    try {
      if (e.tool === 'Read') await touch($, e.file_path, 'read')
      else if (e.tool === 'Edit') await touch($, e.file_path, 'edited')
      else if (e.tool === 'Write') {
        const created = (ran.result as { type?: string } | undefined)?.type === 'create'
        await touch($, e.file_path, created ? 'created' : 'edited')
      } else if (e.tool === 'NotebookEdit') await touch($, e.notebook_path, 'edited')
      else if (e.tool === 'TodoWrite') {
        const list = e.todos.map((t, i) => ({ id: String(i), text: t.content, status: t.status }))
        await update($, todos, () => list)
      } else if (e.tool === 'TaskCreate') {
        const id = (ran.result as { task?: { id?: string } } | undefined)?.task?.id
        if (id) await update($, todos, list => [...list, { id, text: e.subject, status: 'pending' as TodoStatus }])
      } else if (e.tool === 'TaskUpdate') {
        const { taskId, status, subject } = e
        await update($, todos, list =>
          status === 'deleted'
            ? list.filter(t => t.id !== taskId)
            : list.map(t =>
                t.id === taskId ? { ...t, text: subject ?? t.text, status: (status as TodoStatus | undefined) ?? t.status } : t,
              ),
        )
      }

      if (MUTATING.has(e.tool)) await refreshGit($)
    } catch {
      // the panel never gets in the tool's way
    }
    return ran
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const elements = $.ui.resolve(e)
    const { Box, Text, Button } = elements
    // Image exists on the terminal surface (kitty's graphics); elsewhere the alt text shows.
    const Image = (elements as unknown as { Image?: (props: ImageProps & { key?: string }) => ReturnType<typeof Text> })
      .Image
    // 1 column of left margin
    const width = Math.max(18, ((e.props as { bodyColumns?: number }).bodyColumns ?? PANE_COLUMNS) - 1)
    viewedAgent = (e.props as { view?: { agentId?: string } }).view?.agentId
    const { closeButtons } = (await read($, layout)) ?? DEFAULT_LAYOUT
    const [s, g, t, f, S, a, im] = await Promise.all([
      read($, sessions), read($, git), read($, todos), read($, files), textOf($), read($, agents), read($, images),
    ])
    const branchName = (b: string) => (b === DETACHED ? S['panel.detached_head'] : b)
    const TOUCH_MARK: Record<TouchKind, string> = {
      read: S['panel.mark_read'],
      edited: S['panel.mark_edited'],
      created: S['panel.mark_created'],
    }

    const Head = ({ children }: { children: string }) => (
      <Text dimColor bold>
        {children}
      </Text>
    )

    // SESSIONS
    const sessionRows = !s ? (
      <Text dimColor>{S['panel.reading']}</Text>
    ) : s.length === 0 ? (
      <Text dimColor>{S['panel.none_open']}</Text>
    ) : (
      <Box flexDirection="column">
        {groupByTab(s).map(group => (
          <Box key={group.key} flexDirection="column">
            {group.rows.map((row, i) => {
              const look = SESSION_LOOK(row.status)
              const tag = row.isBackground ? ' bg' : ''
              // Sessions sharing a kitty tab are joined by a bracket, as VS Code groups split terminals.
              const n = group.rows.length
              const indent = n < 2 ? '' : i === 0 ? '┌ ' : i === n - 1 ? '└ ' : '├ '
              const label = fitHead(row.title, width - 3 - tag.length - indent.length - (closeButtons ? 2 : 0))
              const pane = row.tmuxPane
              const kitty = row.kitty
              const canSwitch = Boolean(pane || kitty)
              const closeX = closeButtons && kitty
              const withClose = (body: RenderChildren) =>
                closeX ? (
                  <Box key={row.id} flexDirection="row" justifyContent="space-between">
                    {body}
                    <Button key={`close-${row.id}`} plain onPress={() => void closeSession($, row)}>
                      <Text dimColor>×</Text>
                    </Button>
                  </Box>
                ) : (
                  body
                )
              // In kitty or tmux the row is a button: clicking switches to the session.
              if (canSwitch && !row.isSelf)
                return withClose(
                  <Button key={row.id} plain onPress={() => void pressSession($, kitty, pane)}>
                    <Text>
                      <Text dimColor>{indent}</Text>
                      <Text color={look.color}>{look.mark}</Text> {label}
                      {tag && <Text dimColor>{tag}</Text>}
                    </Text>
                  </Button>,
                )
              return withClose(
                <Text key={row.id}>
                  <Text dimColor>{indent}</Text>
                  <Text color={look.color}>{look.mark}</Text>{' '}
                  <Text color={row.isSelf ? 'claude' : undefined} bold={row.isSelf} dimColor={!canSwitch && !row.isSelf}>
                    {label}
                  </Text>
                  {tag && <Text dimColor>{tag}</Text>}
                </Text>,
              )
            })}
          </Box>
        ))}
      </Box>
    )

    // SUBAGENTS
    const AGENT_LOOK = (status = ''): { mark: string; color: string } =>
      status === 'completed'
        ? { mark: '✓', color: 'success' }
        : status === 'failed' || status === 'killed'
          ? { mark: '✗', color: 'error' }
          : { mark: '◐', color: 'permission' }
    const viewable = a.filter(r => r.canView)
    const agentRows =
      a.length === 0 ? (
        <Text dimColor>{S['panel.no_agents']}</Text>
      ) : (
        <Box flexDirection="column">
          {viewedAgent && (
            <Button key="agent-main" hotkey="0" plain onPress={() => void showAgent($)}>
              <Text dimColor>◂ {S['panel.main_conversation']}</Text>
            </Button>
          )}
          {a.map(row => {
            const look = AGENT_LOOK(row.status)
            const name = row.name ?? 'agent'
            const n = viewable.indexOf(row)
            const label = row.label ? fitHead(row.label, Math.max(4, width - cells(name) - 6)) : ''
            const shown = row.id === viewedAgent
            if (!row.canView)
              return (
                <Text key={row.id}>
                  <Text color={look.color}>{look.mark}</Text> {name}
                  {label && <Text dimColor> {label}</Text>}
                </Text>
              )
            return (
              <Button
                key={`agent-${row.id}`}
                hotkey={n >= 0 && n < 9 ? String(n + 1) : undefined}
                plain
                onPress={() => void showAgent($, row.id)}
              >
                <Text color={look.color}>{look.mark}</Text>{' '}
                <Text color={shown ? 'claude' : undefined} bold={shown}>
                  {name}
                </Text>
                {label && <Text dimColor> {label}</Text>}
              </Button>
            )
          })}
        </Box>
      )

    // GIT
    const gitRows = !g ? (
      <Text dimColor>{S['panel.reading']}</Text>
    ) : !g.isRepo ? (
      <Text dimColor>{S['panel.not_a_repo']}</Text>
    ) : (
      <Box flexDirection="column">
        <Text>
          <Text color="claude">⎇ {fitHead(branchName(g.branch), width - 10)}</Text>
          {g.ahead > 0 && <Text color="permission"> ⇡{g.ahead}</Text>}
          {g.behind > 0 && <Text color="warning"> ⇣{g.behind}</Text>}
        </Text>
        {g.files.length === 0 ? (
          <Text dimColor>{S['panel.nothing_changed']}</Text>
        ) : (
          <Text>
            {g.files.length} {g.files.length === 1 ? S['panel.file'] : S['panel.files_count']} <Text color="success">+{g.added}</Text>{' '}
            <Text color="error">−{g.removed}</Text>
          </Text>
        )}
        {g.files.map(file => {
          const label = fileLabel(file.path, width - 3)
          const row = (
            <Text>
              <Text color={GIT_COLOR(file.status)}>{file.status.padEnd(2)}</Text> {label.base}
              {label.dir && <Text dimColor> {label.dir}</Text>}
            </Text>
          )
          // Deleted files have nothing to open.
          if (!g.root || file.status.includes('D')) return row
          const abs = `${g.root}/${file.path.replace(/^.* -> /, '')}`
          return (
            <Button key={`git-${file.path}`} plain onPress={() => void openFile($, abs)}>
              {row}
            </Button>
          )
        })}
        {g.worktrees.map(wt => (
          <Text>
            <Text color="permission">⊞</Text> <Text color="claude">{fitHead(branchName(wt.branch), width - 8)}</Text>
            {wt.changes > 0 ? <Text color="warning"> {wt.changes}</Text> : <Text dimColor> ✓</Text>}
          </Text>
        ))}
      </Box>
    )

    // TASKS
    const done = t.filter(x => x.status === 'completed').length
    const todoRows =
      t.length === 0 ? (
        <Text dimColor>{S['panel.none']}</Text>
      ) : (
        <Box flexDirection="column">
          {t.slice(0, 10).map(item => (
            <Text dimColor={item.status === 'completed'}>
              <Text color={TODO_COLOR[item.status]}>{TODO_MARK[item.status]}</Text> {fitHead(item.text, width - 2)}
            </Text>
          ))}
          {t.length > 10 && <Text dimColor>+{t.length - 10} {S['panel.more_tasks']}</Text>}
        </Box>
      )

    // FILES: every one (the pane scrolls when it doesn't fit)
    const fileRows =
      f.length === 0 ? (
        <Text dimColor>{S['panel.none_yet']}</Text>
      ) : (
        <Box flexDirection="column">
          {f.map(item => {
            const mark = TOUCH_MARK[item.kind]
            const shown = fileLabel(item.path, width - 1 - cells(mark))
            return (
              <Button key={`file-${item.path}`} plain onPress={() => void openFile($, item.abs ?? item.path)}>
                <Text>
                  <Text color={TOUCH_COLOR[item.kind]}>{mark}</Text> {shown.base}
                  {shown.dir && <Text dimColor> {shown.dir}</Text>}
                </Text>
              </Button>
            )
          })}
        </Box>
      )

    // IMAGES: the newest pasted images, as thumbnails (a click opens the image viewer)
    const thumbCols = Math.max(8, width - 1)
    const thumbRows = (img: PastedImage) =>
      img.width && img.height
        ? Math.max(3, Math.min(16, Math.round((thumbCols * img.height) / img.width / 2)))
        : Math.round(thumbCols / 3)
    const imageRows =
      im.length === 0 ? (
        <Text dimColor>{S['panel.no_images']}</Text>
      ) : (
        <Box flexDirection="column" gap={1}>
          {[...im].reverse().slice(0, 3).map(img => (
            <Box key={`img-${img.n}`} flexDirection="column">
              <Button key={`img-open-${img.n}`} plain onPress={() => void openFile($, img.file)}>
                <Text color="claude">[Image #{img.n}]</Text>
              </Button>
              {img.isPng && Image && (
                <Image
                  key={`img-${img.n}-${img.file}`}
                  source={{ file: img.file, format: 'png' }}
                  columns={thumbCols}
                  rows={thumbRows(img)}
                  alt={`[Image #${img.n}]`}
                />
              )}
            </Box>
          ))}
          {im.length > 3 && <Text dimColor>+{im.length - 3}</Text>}
        </Box>
      )

    const blocks: Record<Section, [string, RenderChildren]> = {
      sessions: [S['panel.sessions'], sessionRows],
      agents: [S['panel.agents'], agentRows],
      git: [S['panel.git'], gitRows],
      tasks: [t.length ? `${S['panel.tasks']} ${done}/${t.length}` : S['panel.tasks'], todoRows],
      files: [S['panel.files'], fileRows],
      images: [S['panel.images'], imageRows],
    }
    const { sections } = (await read($, layout)) ?? DEFAULT_LAYOUT
    return (
      <Box flexDirection="column" gap={1} paddingLeft={1}>
        {sections.map(name => (
          <Box key={name} flexDirection="column">
            <Head>{blocks[name][0]}</Head>
            {blocks[name][1]}
          </Box>
        ))}
      </Box>
    )
  })
}
