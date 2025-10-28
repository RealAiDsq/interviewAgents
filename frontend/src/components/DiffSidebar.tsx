import React, { useMemo } from 'react'
import { diffToHtml } from '../utils/diff'

export type Block = {
  id: string
  speaker: string
  timestamp?: string | null
  content: string
  processed: boolean
}

const normalize = (value: string | null | undefined) => (typeof value === 'string' ? value.trim() : '')

const isMeaningfulBlock = (block: Block | undefined): boolean => {
  if (!block) return false
  const speaker = normalize(block.speaker)
  const timestamp = normalize(block.timestamp ?? '')
  if (!speaker || !timestamp) return false
  if (/^\d/.test(speaker)) return false
  if (!timestamp.includes(':')) return false
  return true
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
    const results: { id: string; title: string; html: string }[] = []
    const procList = processed ?? []
    const procById = new Map<string, Block>()
    const consumedIds = new Set<string>()
    const consumedIndexes = new Set<number>()

    procList.forEach((b) => {
      if (b?.id) procById.set(b.id, b)
    })

    const buildTitle = (block: Block | undefined, fallback: string) => {
      if (!block) return fallback
      const parts: string[] = []
      if (block.speaker) parts.push(block.speaker)
      if (block.timestamp) parts.push(`[${block.timestamp}]`)
      if (parts.length) return parts.join(' ')
      return fallback
    }

    original.forEach((orig, index) => {
      if (!isMeaningfulBlock(orig)) return
      const fallbackTitle = `原文块 #${index + 1}`
      const matchById = orig.id ? procById.get(orig.id) : undefined
      const matchByIndex = matchById ? undefined : procList[index]
      const counterpart = matchById ?? matchByIndex

      if (matchById?.id) consumedIds.add(matchById.id)
      if (!matchById && counterpart) consumedIndexes.add(index)

      const left = orig?.content ?? ''
      const right = counterpart?.content ?? ''

      if (counterpart && !isMeaningfulBlock(counterpart)) {
        // counterpart 没有有效 speaker/timestamp 时忽略该块
        return
      }

      if (left !== right) {
        const title = buildTitle(orig, fallbackTitle)
        results.push({ id: orig.id || `original-${index}`, title, html: diffToHtml(left, right) })
      }
    })

    procList.forEach((block, index) => {
      if (!block) return
      if (!isMeaningfulBlock(block)) return
      if ((block.id && consumedIds.has(block.id)) || consumedIndexes.has(index)) return
      const title = buildTitle(block, `新增块 #${index + 1}`)
      const html = diffToHtml('', block.content ?? '')
      results.push({ id: block.id || `processed-${index}`, title, html })
    })

    return results
  }, [original, processed])

  return (
    <>
      {open && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={onClose}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onClose()
            }
          }}
        />
      )}
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
