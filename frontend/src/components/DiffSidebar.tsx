import React, { useMemo } from 'react'
import { diffToHtml } from '../utils/diff'

export type Block = {
  id: string
  speaker: string
  timestamp?: string | null
  content: string
  processed: boolean
}

export default function DiffSidebar({
  open,
  onClose,
  original,
  processed,
  onJump,
}: {
  open: boolean
  onClose: () => void
  original: Block[]
  processed: Block[] | null | undefined
  onJump: (id: string) => void
}) {
  const changed = useMemo(() => {
    const res: { id: string; title: string; html: string }[] = []
    const map: Record<string, Block> = {}
    const proc = processed ?? []
    for (let i = 0; i < proc.length; i++) {
      const b = proc[i]
      if (b && b.id) map[b.id] = b
    }
    for (let i = 0; i < original.length; i++) {
      const b = original[i]
      const pb = map[b.id] ?? proc[i]
      const left = b?.content ?? ''
      const right = pb?.content ?? left
      if (left !== right) {
        const head = `${b.speaker || ''}${b.timestamp ? ' [' + b.timestamp + ']' : ''}` || '未命名'
        res.push({ id: b.id, title: head, html: diffToHtml(left, right) })
      }
    }
    return res
  }, [original, processed])

  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onClose} />}
      <aside className={"sidebar " + (open ? 'open' : '')}>
        <div className="sidebar-head">
          <div>差异（{changed.length}）</div>
          <button onClick={onClose}>关闭</button>
        </div>
        <div className="sidebar-body">
          {changed.length === 0 && <div className="muted">没有检测到改动</div>}
          {changed.map(item => (
            <div key={item.id} className="diff-item">
              <div className="diff-item-head">
                <button className="link" onClick={()=> onJump(item.id)}>{item.title}</button>
              </div>
              <div className="diff-item-content" dangerouslySetInnerHTML={{ __html: item.html }} />
            </div>
          ))}
        </div>
      </aside>
    </>
  )
}
