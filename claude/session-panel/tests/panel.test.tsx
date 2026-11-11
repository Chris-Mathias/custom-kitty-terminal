import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'session-panel',
  component: 'Pane',
  requestId: 'session-panel',
  props: {
    title: 'Session',
    isFocused: false,
    bodyColumns: 40,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

const STATUS = '## main...origin/main [ahead 2]\n M src/main.rs\n?? src/novo.rs\n'
const NUMSTAT = '12\t3\tsrc/main.rs\n'
const WORKTREES =
  'worktree /proj\nHEAD 1\nbranch refs/heads/main\n\n' +
  'worktree /proj/.claude/worktrees/agent-a558ed42b2178b89f\nHEAD 2\nbranch refs/heads/worktree-agent-a558ed42b2178b89f\n'
const AGENTS = JSON.stringify([
  { pid: 1, sessionId: 'aaa', name: 'projetos-51', cwd: '/proj', status: 'busy', kind: 'interactive', startedAt: 1 },
  { pid: 2, sessionId: 'bbb', name: 'seminario-82', cwd: '/x/seminario', status: 'idle', kind: 'interactive', startedAt: 2 },
])

const EN = JSON.stringify({
  'panel.sessions': 'SESSIONS', 'panel.tasks': 'TASKS', 'panel.files': 'FILES', 'panel.files_count': 'files',
  'panel.mark_read': 'R',
})
const PT = JSON.stringify({
  'panel.sessions': 'SESSÕES', 'panel.tasks': 'TAREFAS', 'panel.files': 'ARQUIVOS', 'panel.files_count': 'arquivos',
  'panel.mark_read': 'L',
})
const SETTINGS = '/home/teste/.config/custom-kitty-terminal/settings.json'

type On = Parameters<Parameters<typeof test>[1]>[1]
type Api = Parameters<Parameters<typeof test>[1]>[0]

async function mountPanel($: Api, on: On, files: Record<string, string>) {
  on('command.register', () => ({ value: { command: 'panel' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.close', () => ({ value: undefined }))
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/home/teste' : undefined }))
  // The panel finds the repo's i18n folder through the plugin folder's real path.
  on('fs.stat', () => ({ value: { kind: 'dir', size: 0, mtimeMs: 0, isLink: true, realPath: '/repo/claude/session-panel' } }))
  on('fs.read', (_, e) => {
    const text = files[e.path]
    return text === undefined ? { deny: 'ENOENT: missing' } : { value: text }
  })
  on('fs.list', () => ({ value: [] }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/proj' }))
  on('session.id', () => ({ value: 'aaa' }))
  const tmuxCalls: string[][] = []
  on('process.run', (_, e) => {
    const argv = (e as { argv: string[] }).argv
    if (argv[0] === 'tmux' || argv[0] === 'kitten') tmuxCalls.push([...argv])
    const stdout = argv.includes('agents')
      ? AGENTS
      : argv[0] === 'sh' && argv.includes('panes')
        ? ''
        : argv[0] === 'sh' && argv.includes('kitty')
          ? '2\t7\tunix:@kitty-99\n'
        : argv[0] === 'sh'
          ? 'aaa\tCustomizar o Claude Code\n'
        : argv.includes('--show-toplevel')
          ? '/proj\n'
          : argv.includes('worktree')
            ? WORKTREES
            : argv.includes('-C')
              ? ' M a.rs\n M b.rs\n'
              : argv.includes('status')
                ? STATUS
                : NUMSTAT
    return { value: { exitCode: 0, stdout, stderr: '' } }
  })
  on('tool.call', () => ({ result: {} }))
  on('clock.every', () => ({ value: () => {} }))

  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [
      { content: 'Implementar A*', status: 'in_progress', activeForm: 'Implementando A*' },
      { content: 'Escrever testes', status: 'pending', activeForm: 'Escrevendo testes' },
    ],
  })
  await $.tool.call({ tool: 'Read', file_path: '/proj/Cargo.toml' })
  await $.tool.call({ tool: 'Edit', file_path: '/proj/src/main.rs', old_string: 'a', new_string: 'b' })

  await $.command.run({ command: 'panel' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = async (re: RegExp) => (await ui.find({ type: 'Text', text: re }))?.text
  return { ui, text, tmuxCalls }
}

test('the panel shows sessions, git, tasks and files', async ($, on) => {
  const { ui, text, tmuxCalls } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"en"}',
    '/repo/i18n/en.json': EN,
  })
  expect(await text(/⎇ main/)).toContain('⇡2')
  expect(await text(/ files/)).toContain('+12')
  expect(await text(/^SESSIONS/)).toBe('SESSIONS')
  expect(await text(/^TASKS/)).toBe('TASKS 0/2')
  expect(await text(/Implementar A\*/)).toContain('◐')
  expect(await text(/Customizar/)).toBe('◐ Customizar o Claude Code')
  // seminario-82 runs in kitty (window 7): it's a button that focuses its tab
  await ui.press({ key: 'bbb' })
  expect(tmuxCalls[0]).toEqual(['kitten', '@', '--to', 'unix:@kitty-99', 'focus-window', '--match', 'id:7'])
  expect(await text(/worktree-agent-a558ed/)).toBe('⊞ worktree-agent-a558ed 2')
  expect(await text(/^E main\.rs/)).toBe('E main.rs src')
  expect(await text(/Cargo\.toml/)).toBe('R Cargo.toml')
  await ui.unmount()
})

test('the panel speaks Portuguese when the settings say so', async ($, on) => {
  const { ui, text } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"pt"}',
    '/repo/i18n/en.json': EN,
    '/repo/i18n/pt.json': PT,
  })
  expect(await text(/^SESSÕES/)).toBe('SESSÕES')
  expect(await text(/^TAREFAS/)).toBe('TAREFAS 0/2')
  expect(await text(/arquivos/)).toContain('+12')
  expect(await text(/Cargo\.toml/)).toBe('L Cargo.toml')
  await ui.unmount()
})

test('the panel falls back to English when nothing can be read', async ($, on) => {
  const { ui, text } = await mountPanel($, on, {})
  expect(await text(/^TASKS/)).toBe('TASKS 0/2')
  expect(await text(/Cargo\.toml/)).toBe('R Cargo.toml')
  await ui.unmount()
})
