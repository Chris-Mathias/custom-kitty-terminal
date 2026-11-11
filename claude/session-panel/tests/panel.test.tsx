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
// kitty: window 5 (session aaa) and window 7 (session bbb) share the second tab.
const KITTY_LS = JSON.stringify([
  {
    tabs: [
      { id: 1, title: 'Monorepo', windows: [{ id: 3 }] },
      { id: 2, title: 'Incerti', windows: [{ id: 5 }, { id: 7 }] },
    ],
  },
])

type On = Parameters<Parameters<typeof test>[1]>[1]
type Api = Parameters<Parameters<typeof test>[1]>[0]

async function mountPanel(
  $: Api,
  on: On,
  files: Record<string, unknown>,
  status = STATUS,
  opts: {
    skipCommand?: boolean
    agents?: unknown[]
    view?: { agentId?: string }
    lists?: Record<string, { name: string; kind: string }[]>
  } = {},
) {
  const opened: unknown[] = []
  const views: unknown[] = []
  on('agent.list', () => ({ value: opts.agents ?? [] }))
  on('ui.view', (_, e) => (views.push(e), { value: {} }))
  on('command.register', () => ({ value: { command: 'panel' } }))
  on('ui.open', (_, e) => (opened.push(e), { value: { isPlaced: true } }))
  on('ui.close', () => ({ value: undefined }))
  on('env.get', (_, e) => ({ value: e.name === 'HOME' ? '/home/teste' : undefined }))
  // The panel finds the repo's i18n folder through the plugin folder's real path.
  on('fs.stat', () => ({
    value: { kind: 'dir', size: 0, mtimeMs: Date.now(), isLink: true, realPath: '/repo/claude/session-panel' },
  }))
  on('fs.read', (_, e) => {
    const text = files[e.path]
    return text === undefined ? { deny: 'ENOENT: missing' } : { value: text }
  })
  on('fs.list', (_, e) => ({ value: opts.lists?.[(e as { path: string }).path] ?? [] }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/proj' }))
  on('session.id', () => ({ value: 'aaa' }))
  const tmuxCalls: string[][] = []
  const opens: string[] = []
  on('process.run', (_, e) => {
    const argv = (e as { argv: string[] }).argv
    if ((argv[0] === 'tmux' || argv[0] === 'kitten') && !argv.includes('ls')) tmuxCalls.push([...argv])
    if (argv[0] === 'sh' && argv.includes('ckt-open')) {
      opens.push(argv[argv.length - 1]!)
      return { value: { exitCode: 0, stdout: '', stderr: '' } }
    }
    const stdout = argv.includes('agents')
      ? AGENTS
      : argv[0] === 'sh' && argv.includes('panes')
        ? ''
        : argv[0] === 'kitten' && argv.includes('ls')
          ? KITTY_LS
        : argv[0] === 'sh' && argv.includes('kitty')
          ? '1\t5\tunix:@kitty-99\n2\t7\tunix:@kitty-99\n'
        : argv[0] === 'sh'
          ? 'aaa\tCustomizar o Claude Code\n'
        : argv.includes('--show-toplevel')
          ? '/proj\n'
          : argv.includes('worktree')
            ? WORKTREES
            : argv.includes('-C')
              ? ' M a.rs\n M b.rs\n'
              : argv.includes('status')
                ? status
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

  if (opts.skipCommand) return { ui: undefined as never, text: undefined as never, tmuxCalls, opened, views, opens }
  await $.command.run({ command: 'panel' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal', props: { ...PANE.props, view: opts.view ?? {} } })
  const text = async (re: RegExp) => (await ui.find({ type: 'Text', text: re }))?.text
  return { ui, text, tmuxCalls, opened, views, opens }
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
  expect(await text(/Customizar/)).toBe('┌ ◐ Customizar o Claude Code')
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

test('the panel speaks Chinese and keeps wide text inside the pane', async ($, on) => {
  const ZH = JSON.stringify({ 'panel.tasks': '任务', 'panel.files_count': '个文件', 'panel.mark_read': '读' })
  const { ui, text } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"zh"}',
    '/repo/i18n/en.json': EN,
    '/repo/i18n/zh.json': ZH,
  })
  expect(await text(/^任务/)).toBe('任务 0/2')
  expect(await text(/Cargo\.toml/)).toBe('读 Cargo.toml')
  await $.tool.call({ tool: 'Read', file_path: '/proj/文档/' + '很长的中文文件名'.repeat(4) + '.md' })
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: '检查拉取请求并修复问题'.repeat(3), status: 'pending', activeForm: '检查中' }],
  })
  // Chinese characters take two columns; the pane body is 40 wide.
  const cols = (s: string) => [...s].reduce((n, ch) => n + (/[　-鿿＀-｠]/.test(ch) ? 2 : 1), 0)
  const task = (await text(/^○ 检查/)) ?? ''
  const file = (await text(/^读 很长/)) ?? ''
  expect(task).toContain('…')
  expect(file).toContain('…')
  expect(cols(task)).toBeLessThanOrEqual(39)
  expect(cols(file)).toBeLessThanOrEqual(39)
  await ui.unmount()
})

test('the panel falls back to English when nothing can be read', async ($, on) => {
  const { ui, text } = await mountPanel($, on, {})
  expect(await text(/^TASKS/)).toBe('TASKS 0/2')
  expect(await text(/Cargo\.toml/)).toBe('R Cargo.toml')
  await ui.unmount()
})

test('the git section lists every changed file (the pane scrolls)', async ($, on) => {
  const many = '## main\n' + Array.from({ length: 12 }, (_, i) => ` M src/file${i}.rs`).join('\n') + '\n'
  const { ui, text } = await mountPanel($, on, {}, many)
  expect(await text(/file11\.rs/)).toBe('M  file11.rs src')
  expect(await text(/more$/)).toBeUndefined()
  await ui.unmount()
})

test('the panel follows the section order and visibility from the settings', async ($, on) => {
  const { ui } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"en","panel":{"sections":["files","git"]}}',
    '/repo/i18n/en.json': EN,
  })
  const heads = (await ui.findAll({ type: 'Text', text: /^(SESSIONS|GIT|TASKS|FILES)/ })).map(t => t.text)
  expect(heads).toEqual(['FILES', 'GIT'])
  await ui.unmount()
})

test('the panel stays closed at start when auto open is off', async ($, on) => {
  const { opened } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"en","panel":{"auto_open":false}}',
    '/repo/i18n/en.json': EN,
  }, STATUS, { skipCommand: true })
  expect(opened.length).toBe(0)
})

test('the panel lists the running subagents', async ($, on) => {
  const agents = JSON.stringify([
    { id: 'a1', name: 'general-purpose', label: 'Fixing the parser', status: 'running', startTime: 1, tokenCount: 7 },
  ])
  const { ui, text } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"en"}',
    '/repo/i18n/en.json': EN,
    '/home/teste/.cache/custom-kitty-terminal/agents/aaa.json': agents,
  })
  expect(await text(/general-purpose/)).toBe('◐ general-purpose Fixing the parser')
  await ui.unmount()
})

const SUBAGENTS = [
  { id: 'ag1', description: 'Implement Task 8', type: 'general-purpose', status: 'running' },
  { id: 'ag2', description: 'Review Task 1', type: 'code-reviewer', status: 'completed' },
]

test('pressing a subagent shows its conversation', async ($, on) => {
  const { ui, views } = await mountPanel($, on, { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN }, STATUS, {
    agents: SUBAGENTS,
  })
  await ui.press({ key: 'agent-ag2' })
  expect(views).toEqual([{ agentId: 'ag2' }])
  await ui.unmount()
})

test('a digit picks a subagent and 0 goes back to the main conversation', async ($, on) => {
  const { ui, views } = await mountPanel($, on, { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN }, STATUS, {
    agents: SUBAGENTS,
    view: { agentId: 'ag1' },
  })
  await ui.press({ key: 'agent-main' })
  expect(views).toEqual([{}])
  expect((await ui.find({ type: 'Button', key: 'agent-ag1' }))?.props.hotkey).toBe('1')
  expect((await ui.find({ type: 'Button', key: 'agent-main' }))?.props.hotkey).toBe('0')
  await ui.unmount()
})

test('/agent next and /agent main switch the view', async ($, on) => {
  const { views } = await mountPanel($, on, { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN }, STATUS, {
    agents: SUBAGENTS,
  })
  await $.command.run({ command: 'agent', args: 'next' })
  await $.command.run({ command: 'agent', args: '2' })
  await $.command.run({ command: 'agent', args: 'main' })
  expect(views).toEqual([{ agentId: 'ag1' }, { agentId: 'ag2' }, {}])
})

test('sessions in the same kitty tab are joined by a bracket, like VS Code', async ($, on) => {
  const { ui, text } = await mountPanel($, on, { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN })
  expect(await text(/Customizar/)).toBe('┌ ◐ Customizar o Claude Code')
  expect(await text(/seminario/)).toBe('└ ○ seminario-82')
  expect(await text(/Incerti/)).toBeUndefined() // no tab header
  await ui.unmount()
})

test('with the option on, the x of a session asks to close it in its own tab', async ($, on) => {
  const { ui, tmuxCalls } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"en","panel_close_buttons":true}',
    '/repo/i18n/en.json': EN,
  })
  await ui.press({ key: 'close-bbb' })
  expect(tmuxCalls.at(-1)).toEqual([
    'kitten', '@', '--to', 'unix:@kitty-99', 'launch', '--type=overlay', '--match', 'id:7',
    '/home/teste/.config/kitty/close-tab-dialog.sh', 'window:7', 'Claude Code · seminario-82',
  ])
  await ui.unmount()
})

test('with confirmation set to never, the x closes the session right away', async ($, on) => {
  const { ui, tmuxCalls } = await mountPanel($, on, {
    [SETTINGS]: '{"language":"en","panel_close_buttons":true,"confirm_close":"never"}',
    '/repo/i18n/en.json': EN,
  })
  await ui.press({ key: 'close-bbb' })
  expect(tmuxCalls.at(-1)).toEqual(['kitten', '@', '--to', 'unix:@kitty-99', 'close-window', '--match', 'id:7'])
  await ui.unmount()
})

test('the x is not drawn when the option is off', async ($, on) => {
  const { ui } = await mountPanel($, on, { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN })
  expect(await ui.find({ type: 'Button', key: 'close-bbb' })).toBeUndefined()
  await ui.unmount()
})

test('clicking a file (FILES or GIT) opens it in the editor through ckt-open', async ($, on) => {
  const { ui, opens } = await mountPanel($, on, { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN })
  await ui.press({ key: 'file-Cargo.toml' })
  await ui.press({ key: 'git-src/main.rs' })
  expect(opens).toEqual(['/proj/Cargo.toml', '/proj/src/main.rs'])
  await ui.unmount()
})

test('images pasted earlier in the session show with their number', async ($, on) => {
  // A PNG header that says 800 x 400.
  const png = btoa(
    String.fromCharCode(0x89, 0x50, 0x4e, 0x47, 13, 10, 26, 10, 0, 0, 0, 13, 0x49, 0x48, 0x44, 0x52, 0, 0, 3, 0x20, 0, 0, 1, 0x90),
  )
  const dir = '/home/teste/.cache/custom-kitty-terminal/images/aaa'
  const { ui, text, opens } = await mountPanel(
    $,
    on,
    { [SETTINGS]: '{"language":"en"}', '/repo/i18n/en.json': EN, [`${dir}/3.png`]: { base64: png } },
    STATUS,
    { lists: { [dir]: [{ name: '3.png', kind: 'file' }, { name: 'notes.txt', kind: 'file' }] } },
  )
  expect(await text(/^IMAGES/)).toBe('IMAGES')
  expect(await text(/Image #3/)).toBe('[Image #3]')
  await ui.press({ key: 'img-open-3' })
  expect(opens).toEqual([`${dir}/3.png`])
  await ui.unmount()
})
