export type TodoStatus = 'pending' | 'in_progress' | 'completed'
export type Todo = { id: string; text: string; status: TodoStatus }

export type TouchKind = 'read' | 'edited' | 'created'
export type FileTouch = { path: string; kind: TouchKind; at: number }

export type GitFile = { status: string; path: string }
export type GitInfo = {
  isRepo: boolean
  branch: string
  ahead: number
  behind: number
  files: GitFile[]
  added: number
  removed: number
  worktrees: Worktree[]
}

export type Worktree = { name: string; branch: string; changes: number }

export type SessionRow = {
  id: string
  name: string
  title: string
  folder: string
  status: string
  isBackground: boolean
  isSelf: boolean
  /** tmux pane the session runs in (e.g. %3); absent outside tmux */
  tmuxPane?: string
  /** kitty window the session runs in and its control socket */
  kitty?: { window: string; socket: string }
  /** kitty tab the window is in: number and title, as the tab bar shows them */
  tab?: { key: string; label: string; order: number }
}

declare module 'claude-code' {
  interface PluginState {
    'session-panel': {
      todos: Shaped<Todo[]>
      files: Shaped<FileTouch[]>
      git: Shaped<GitInfo | null>
      sessions: Shaped<SessionRow[] | null>
      strings: Shaped<Record<string, string>>
      agents: Shaped<{ id: string; name?: string; label?: string; status?: string; canView?: boolean }[]>
      layout: Shaped<{
        sections: ('sessions' | 'agents' | 'git' | 'tasks' | 'files')[]
        autoOpen: boolean
        closeButtons: boolean
        confirmClose: string
      } | null>
    }
  }
}
