export type TodoStatus = 'pending' | 'in_progress' | 'completed'
export type Todo = { id: string; text: string; status: TodoStatus }

export type TouchKind = 'read' | 'edited' | 'created'
/** path: as shown (relative to the session's folder when inside it); abs: what opens */
export type FileTouch = { path: string; abs: string; kind: TouchKind; at: number }

/** An image pasted into this Claude session: its [Image #n], the saved copy and its size */
export type PastedImage = { n: number; file: string; isPng: boolean; width?: number; height?: number }

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
  /** the repository's top folder: git's paths are relative to it */
  root?: string
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
      images: Shaped<PastedImage[]>
      git: Shaped<GitInfo | null>
      sessions: Shaped<SessionRow[] | null>
      strings: Shaped<Record<string, string>>
      agents: Shaped<{ id: string; name?: string; label?: string; status?: string; canView?: boolean }[]>
      layout: Shaped<{
        sections: ('sessions' | 'agents' | 'git' | 'tasks' | 'files' | 'images')[]
        autoOpen: boolean
        closeButtons: boolean
        confirmClose: string
      } | null>
    }
  }
}
