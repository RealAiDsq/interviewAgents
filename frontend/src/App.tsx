import React, { useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import DiffSidebar from './components/DiffSidebar'

type Block = {
  id: string
  speaker: string
  timestamp?: string | null
  content: string
  processed: boolean
}

type Doc = { blocks: Block[] }

export default function App() {
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileName, setFileName] = useState('')
  const [doc, setDoc] = useState<Doc | null>(null)
  const [processed, setProcessed] = useState<Doc | null>(null)
  const [tab, setTab] = useState<'raw' | 'processed'>('raw')
  const [md, setMd] = useState('')
  const [loading, setLoading] = useState(false)
  const [dropActive, setDropActive] = useState(false)
  const [renderKey, setRenderKey] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [toasts, setToasts] = useState<{ id: number, type: 'error' | 'success' | 'info', text: string }[]>([])
  const [diffOpen, setDiffOpen] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [editing, setEditing] = useState<Record<string, boolean>>({})
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const saveTimers = useRef<Record<string, any>>({})

  const canExport = useMemo(() => (tab === 'processed' ? processed : doc) != null, [tab, doc, processed])

  function baseName(name: string) {
    const i = name.lastIndexOf('.')
    return i > 0 ? name.slice(0, i) : name
  }

  function addToast(type: 'error' | 'success' | 'info', text: string) {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, type, text }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3000)
  }

  function toBlockquote(txt: string): string {
    const lines = (txt || '').split(/\r?\n/)
    if (!lines.length) return '>'
    return lines.map(ln => ln.trim() ? `> ${ln}` : '>').join('\n')
  }

  async function onUpload(f?: File | null) {
    const target = f ?? file
    if (!target) return
    const form = new FormData()
    form.append('file', target)
    setLoading(true)
    setUploadProgress(0)
    try {
      const res = await axios.post('/api/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setUploadProgress(Math.round((e.loaded / e.total) * 100))
        }
      })
      setDoc(res.data)
      setProcessed(null)
      setTab('raw')
      setMd(await renderMarkdown(res.data, 'raw'))
      // 自动标题：用文件名（去后缀）
      if (!title && (target.name)) setTitle(baseName(target.name))
      setRenderKey(k => k + 1)
      addToast('success', '解析完成')
    } catch (e: any) {
      addToast('error', '上传解析失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
      setTimeout(() => setUploadProgress(0), 500)
    }
  }

  async function renderMarkdown(d: Doc, mode: 'raw' | 'processed') {
    const res = await axios.post('/api/preview?mode=' + mode, { blocks: d.blocks, title })
    return res.data.markdown as string
  }

  async function onProcess() {
    if (!doc) return
    setLoading(true)
    try {
      await processStream()
    } catch (e: any) {
      addToast('error', '流式处理失败，回退本地规则: ' + (e?.message || e))
      try {
        const rule = await axios.post('/api/process', { mode: 'rule', blocks: doc.blocks })
        setProcessed(rule.data as Doc)
        setTab('processed')
        setMd(await renderMarkdown(rule.data as any, 'processed'))
      } catch (ee:any) {
        addToast('error', '本地规则处理也失败: ' + (ee?.response?.data?.detail || ee.message))
      }
    } finally {
      setLoading(false)
    }
  }

  async function processStream() {
    if (!doc) return
    // 初始化 processed 容器
    const base = { blocks: doc.blocks.map(b => ({...b, content: '', processed: false})) }
    setProcessed(base)
    setTab('processed')

    const res = await fetch('/api/process/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ blocks: doc.blocks, provider: 'zhipu' })
    })
    if (!res.body) throw new Error('无响应体')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const applyDelta = (id: string, text: string) => {
      setProcessed(prev => {
        if (!prev) return prev
        const blocks = prev.blocks.map(b => b.id===id ? ({...b, content: (b.content||'') + text}) : b)
        return { blocks }
      })
    }
    const markEnd = (id: string, text: string) => {
      setProcessed(prev => {
        if (!prev) return prev
        const blocks = prev.blocks.map(b => b.id===id ? ({...b, content: text || b.content, processed: true}) : b)
        return { blocks }
      })
    }

    const emit = (event: string, data: any) => {
      if (event === 'delta') {
        applyDelta(data.id, data.text || '')
      } else if (event === 'block_end') {
        markEnd(data.id, data.text || '')
      }
    }

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        const lines = raw.split('\n')
        let event = 'message'
        let data = ''
        for (const ln of lines) {
          if (ln.startsWith('event:')) event = ln.slice(6).trim()
          else if (ln.startsWith('data:')) data += ln.slice(5).trim()
        }
        if (data) {
          try { emit(event, JSON.parse(data)) } catch {}
        }
      }
    }
    addToast('success', '流式处理完成')
  }

  async function onSwitchTab(next: 'raw' | 'processed') {
    setTab(next)
    const d = next === 'processed' ? processed : doc
    if (d) {
      setMd(await renderMarkdown(d, next))
      setRenderKey(k => k + 1)
    }
  }

  async function onExport(fmt: 'md' | 'docx' | 'pdf') {
    const d = (tab === 'processed' ? processed : doc)
    if (!d) return
    try {
      const res = await axios.post('/api/export?fmt=' + fmt, { blocks: d.blocks, title }, { responseType: fmt === 'md' ? 'text' : 'blob' })
      if (fmt === 'md') {
        const blob = new Blob([res.data], { type: 'text/markdown' })
        download(blob, (title || 'export') + '.md')
      } else if (fmt === 'docx') {
        download(res.data, (title || 'export') + '.docx')
      } else {
        download(res.data, (title || 'export') + '.pdf')
      }
      addToast('success', '导出完成')
    } catch (e: any) {
      addToast('error', '导出失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  function download(blob: Blob, filename: string) {
    const a = document.createElement('a')
    const url = URL.createObjectURL(blob)
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  function startEdit(b: Block) {
    setEditing(s => ({ ...s, [b.id]: true }))
    setDrafts(d => ({ ...d, [b.id]: (tab==='processed' ? (processed?.blocks.find(x=>x.id===b.id)?.content ?? b.content) : b.content) }))
  }

  async function saveBlock(id: string) {
    const text = drafts[id] ?? ''
    const curr = (tab === 'processed' ? (processed?.blocks?.length ? processed! : { blocks: doc!.blocks.map(x=>({...x})) }) : (doc || { blocks: [] }))
    const newBlocks = curr.blocks.map(x => x.id === id ? { ...x, content: text, processed: true } : x)
    const newDoc = { blocks: newBlocks }
    if (tab === 'processed') setProcessed(newDoc)
    else setDoc(newDoc)
    setMd(await renderMarkdown(newDoc as any, tab))
    setRenderKey(k=>k+1)
    addToast('success', '已自动保存')
  }

  function onDraftChange(id: string, v: string) {
    setDrafts(d => ({ ...d, [id]: v }))
    if (saveTimers.current[id]) clearTimeout(saveTimers.current[id])
    // 自动保存但不退出编辑态（保持当前行为）
    saveTimers.current[id] = setTimeout(async () => {
      await saveBlock(id)
    }, 1200)
  }

  // 全局 click-away：点击编辑块外部则保存并退出编辑态
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      // 若当前没有处于编辑的块，忽略
      const editingIds = Object.keys(editing).filter(k => editing[k])
      if (!editingIds.length) return
      const target = e.target as HTMLElement | null
      if (!target) return
      // 向上寻找最近的块容器 .blk-slim
      let el: HTMLElement | null = target
      let insideEditing = false
      while (el) {
        if (el.classList && el.classList.contains('blk-slim')) {
          const bid = (el.id || '').startsWith('blk-') ? el.id.slice(4) : ''
          if (bid && editing[bid]) insideEditing = true
          break
        }
        el = el.parentElement
      }
      if (!insideEditing) {
        // 点击在所有编辑块之外：保存并退出所有编辑块
        editingIds.forEach(async (id) => {
          try { await saveBlock(id) } catch {}
          endEdit(id)
        })
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [editing])

  function endEdit(id: string) {
    setEditing(s => ({ ...s, [id]: false }))
  }

  function renderPreviewBlocks() {
    const blocks = (tab === 'processed' ? processed?.blocks : doc?.blocks) || []
    if (!blocks.length) return (<div className="preview markdown"><em>暂无内容，请上传文件</em></div>)
    return (
      <div className="preview markdown">
        {blocks.map((b, idx) => {
          const header = `${b.speaker || ''}${b.timestamp ? ' ['+b.timestamp+']' : ''}`
          const isEdit = !!editing[b.id]
          const value = drafts[b.id] ?? b.content
          const mdBlock = (header ? `### ${header}\n\n` : '') + (isEdit ? '' : toBlockquote(b.content))
          return (
            <div key={b.id} id={`blk-${b.id}`} className="blk-slim" onDoubleClick={()=> startEdit(b)}>
              {isEdit ? (
                <div>
                  {header ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{`### ${header}`}</ReactMarkdown> : null}
                  <textarea
                    value={value}
                    onChange={e=> onDraftChange(b.id, e.target.value)}
                    onBlur={async ()=>{ await saveBlock(b.id); endEdit(b.id) }}
                    placeholder="双击进入编辑，失焦或1.2秒无输入自动保存"
                  />
                </div>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{mdBlock}</ReactMarkdown>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="layout">
      <div className="left">
        <div className="left-header">
          <h1>采访稿处理助手</h1>
        </div>
        <div className="box">
          <label>文档标题</label>
          <input type="text" placeholder="可选" value={title} onChange={e => setTitle(e.target.value)} />
        </div>

        <div className="box">
          <label>选择采访稿（自动解析，支持 .txt/.md/.doc/.docx）</label>
          <div
            className={"dropzone " + (dropActive ? 'active' : '')}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDropActive(true) }}
            onDragEnter={e => { e.preventDefault(); setDropActive(true) }}
            onDragLeave={e => { e.preventDefault(); setDropActive(false) }}
            onDrop={async e => {
              e.preventDefault(); setDropActive(false)
              const f = e.dataTransfer.files?.[0]
              if (f) {
                setFile(f)
                setFileName(f.name)
                setTitle(baseName(f.name))
                await onUpload(f)
              }
            }}
            role="button"
            aria-label="拖拽或点击选择文件"
          >
            <div className="dz-icon">📄</div>
            <div className="dz-title">拖拽文件到此处，或点击选择</div>
            <div className="dz-sub">支持 .txt / .md / .doc / .docx</div>
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: 'none' }}
              onChange={async e => { const f = e.target.files?.[0] || null; setFile(f); setFileName(f?.name || ''); if (f) { setTitle(baseName(f.name)); await onUpload(f) } }}
            />
          </div>
          {fileName && <div className="fileName">{fileName}（已自动解析）</div>}
        </div>

        <div className="box">
          <label>处理操作</label>
          <div className="row">
            <button onClick={onProcess} className="primary" disabled={!doc || loading}>语义清理与规范化</button>
          </div>
        </div>

        <div className="box">
          <label>导出</label>
          <div className="row">
            <button onClick={() => onExport('md')} disabled={!canExport}>导出 Markdown</button>
            <button onClick={() => onExport('docx')} disabled={!canExport}>导出 Word</button>
            <button onClick={() => onExport('pdf')} disabled={!canExport}>导出 PDF</button>
          </div>
        </div>
      </div>

      <div className="right">
        <div className="toolbar">
          <div className="segmented">
            <button className={tab === 'raw' ? 'active' : ''} onClick={() => onSwitchTab('raw')}>解析结果</button>
            <button className={tab === 'processed' ? 'active' : ''} onClick={() => onSwitchTab('processed')}>处理结果</button>
          </div>
          <div className="right-actions">
            <button onClick={()=> setDiffOpen(true)}>差异</button>
            <div className="spinner-wrap">{loading ? <span className="spinner" /> : ''}</div>
          </div>
        </div>
        {uploadProgress>0 && <div className="upload-progress"><div className="bar" style={{width: uploadProgress+'%'}}></div></div>}
        <div key={renderKey} className="fade-in">
          {renderPreviewBlocks()}
        </div>
        {/* Diff sidebar triggers from toolbar; no inline diff in page */}
      </div>
      {/* Toasts */}
      <div className="toasts">
        {toasts.map(t=> (
          <div key={t.id} className={`toast ${t.type}`}>{t.text}</div>
        ))}
      </div>
      <DiffSidebar
        open={diffOpen}
        onClose={()=> setDiffOpen(false)}
        original={doc?.blocks || []}
        processed={processed?.blocks || []}
        onJump={(id)=>{
          const el = document.getElementById('blk-'+id)
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          setDiffOpen(false)
        }}
      />
      {/* Theme floating button at bottom-left */}
      <div className="theme-fab">
        <button className="icon-btn" title={theme==='dark'?'切换为浅色':'切换为深色'} onClick={()=>{
          const v = theme==='dark' ? 'light' : 'dark'
          setTheme(v as any)
          document.documentElement.setAttribute('data-theme', v)
        }}>
          <img src={theme==='dark'? '/icons/sun.svg' : '/icons/moon.svg'} alt="主题" />
        </button>
      </div>
    </div>
  )
}
