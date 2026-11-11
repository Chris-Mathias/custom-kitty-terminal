import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register } from 'claude-code'

import type { FileTouch, GitInfo, SessionRow, Todo, TodoStatus, TouchKind, Worktree } from '../types'

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
const SECTIONS = ['sessions', 'git', 'tasks', 'files'] as const
type Section = (typeof SECTIONS)[number]
type Layout = { sections: Section[]; autoOpen: boolean }
const DEFAULT_LAYOUT: Layout = { sections: [...SECTIONS], autoOpen: true }

async function readSettings($: Engine): Promise<Record<string, unknown>> {
  const dir = (await $.env.get('CKT_CONFIG_DIR')) || `${await $.env.get('HOME')}/.config/custom-kitty-terminal`
  return readJson($, `${dir}/settings.json`)
}

function layoutOf(settings: Record<string, unknown>): Layout {
  const panel = (settings.panel ?? {}) as { sections?: unknown; auto_open?: unknown }
  const sections = Array.isArray(panel.sections)
    ? (panel.sections as unknown[]).filter(
        (x, i, all): x is Section => SECTIONS.includes(x as Section) && all.indexOf(x) === i,
      )
    : [...SECTIONS]
  return { sections, autoOpen: typeof panel.auto_open === 'boolean' ? panel.auto_open : true }
}

async function loadStrings($: Engine): Promise<Strings> {
  try {
    const settings = await readSettings($)
    await update($, layout, () => layoutOf(settings))
    const lang = settings.language === 'pt' ? 'pt' : 'en'
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
const files = atom({ plugin: 'session-panel', key: 'files' } as const, [] as FileTouch[], { shape: 'files-2' })
const git = atom({ plugin: 'session-panel', key: 'git' } as const, null as GitInfo | null, { shape: 'git-2' })
const sessions = atom({ plugin: 'session-panel', key: 'sessions' } as const, null as SessionRow[] | null, {
  shape: 'sessions-4',
})
const strings = atom({ plugin: 'session-panel', key: 'strings' } as const, {} as Record<string, string>, {
  shape: 'strings-1',
})
const layout = atom({ plugin: 'session-panel', key: 'layout' } as const, null as Layout | null, { shape: 'layout-1' })
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
  return { isRepo: true, branch, ahead, behind, files: changed, added, removed, worktrees: await readWorktrees($) }
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
        }),
      )
    await update($, sessions, () => list)
  } catch {
    // claude not on PATH or unexpected output: keep the last value
  }
}

// ---------- files and tasks ----------
async function touch($: Engine, rawPath: string, kind: TouchKind) {
  const cwd = await $.session.cwd()
  const path = rawPath.startsWith(cwd + '/') ? rawPath.slice(cwd.length + 1) : rawPath
  await update($, files, list => {
    const old = list.find(f => f.path === path)
    const best = old && KIND_RANK[old.kind] > KIND_RANK[kind] ? old.kind : kind
    return [{ path, kind: best, at: Date.now() }, ...list.filter(f => f.path !== path)].slice(0, 60)
  })
}

// ---------- drawing ----------
// Truncates at the end, for text (tasks, names).
const fitHead = (s: string, n: number) => (s.length <= n ? s : s.slice(0, Math.max(1, n - 1)) + '…')

// File name and, if it fits, its folder (drawn dimmed): "register.tsx hooks"
const fileLabel = (path: string, n: number): { base: string; dir?: string } => {
  const parts = path.split('/')
  const base = parts.pop() ?? path
  const dir = parts.pop()
  if (base.length >= n) return { base: fitHead(base, n) }
  return dir && base.length + 1 + dir.length <= n ? { base, dir } : { base }
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
    if (((await read($, layout)) ?? DEFAULT_LAYOUT).autoOpen) void $.ui.open(open(S))
    // The language can change from the settings menu while the session runs.
    $.clock.every(5000, () => void refreshStrings($))

    void refreshGit($)
    void refreshSessions($)
    $.clock.every(15000, () => void refreshGit($))
    // Sessions: the state (busy/idle) is re-read every 4 s; opening or
    // closing a session is noticed in ~1 s by watching the folder where Claude Code
    // records each open session (~/.claude/sessions, one file per process).
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
    const { Box, Text, Button } = $.ui.resolve(e)
    // 1 column of left margin
    const width = Math.max(18, ((e.props as { bodyColumns?: number }).bodyColumns ?? PANE_COLUMNS) - 1)
    const [s, g, t, f, S] = await Promise.all([read($, sessions), read($, git), read($, todos), read($, files), textOf($)])
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
        {s.map(row => {
          const look = SESSION_LOOK(row.status)
          const tag = row.isBackground ? ' bg' : ''
          const label = fitHead(row.title, width - 3 - tag.length)
          const pane = row.tmuxPane
          const kitty = row.kitty
          const canSwitch = Boolean(pane || kitty)
          // In kitty or tmux the row is a button: clicking switches to the session.
          if (canSwitch && !row.isSelf)
            return (
              <Button
                key={row.id}
                plain
                onPress={() => void pressSession($, kitty, pane)}
              >
                <Text color={look.color}>{look.mark}</Text> {label}
                {tag && <Text dimColor>{tag}</Text>}
              </Button>
            )
          return (
            <Text>
              <Text color={look.color}>{look.mark}</Text>{' '}
              <Text color={row.isSelf ? 'claude' : undefined} bold={row.isSelf} dimColor={!canSwitch && !row.isSelf}>
                {label}
              </Text>
              {tag && <Text dimColor>{tag}</Text>}
            </Text>
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
        {g.files.map(file => (
          <Text>
            <Text color={GIT_COLOR(file.status)}>{file.status.padEnd(2)}</Text> {fileLabel(file.path, width - 3).base}
            {fileLabel(file.path, width - 3).dir && <Text dimColor> {fileLabel(file.path, width - 3).dir}</Text>}
          </Text>
        ))}
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
          {f.map(item => (
            <Text>
              <Text color={TOUCH_COLOR[item.kind]}>{TOUCH_MARK[item.kind]}</Text> {fileLabel(item.path, width - 2).base}
              {fileLabel(item.path, width - 2).dir && <Text dimColor> {fileLabel(item.path, width - 2).dir}</Text>}
            </Text>
          ))}
        </Box>
      )

    const blocks: Record<Section, [string, unknown]> = {
      sessions: [S['panel.sessions'], sessionRows],
      git: [S['panel.git'], gitRows],
      tasks: [t.length ? `${S['panel.tasks']} ${done}/${t.length}` : S['panel.tasks'], todoRows],
      files: [S['panel.files'], fileRows],
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
