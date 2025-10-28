import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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

type LLMModel = {
  id: string
  label: string
  context_window?: string
}

type LLMProvider = {
  provider: string
  label: string
  default_model?: string | null
  models: LLMModel[]
}

type LLMDefaults = {
  provider?: string | null
  model?: string | null
  temperature?: number
  system_prompt?: string
  parallel?: number
  parallelism?: number
  parallel_max?: number
}

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
  const [speakers, setSpeakers] = useState<string[]>([])
  const saveTimers = useRef<Record<string, any>>({})

  const [providerCatalog, setProviderCatalog] = useState<LLMProvider[]>([])
  const [selectedProvider, setSelectedProvider] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [temperature, setTemperature] = useState(0.3)
  const [systemPrompt, setSystemPrompt] = useState('')
  const [defaultSystemPrompt, setDefaultSystemPrompt] = useState('')
  const [catalogLoaded, setCatalogLoaded] = useState(false)
  const [modelOptions, setModelOptions] = useState<Record<string, LLMModel[]>>({})
  const [modelLoading, setModelLoading] = useState(false)
  const [processingProgress, setProcessingProgress] = useState(0)
  const processingResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const completedBlocksRef = useRef(0)
  const [parallelism, setParallelism] = useState(1)
  const [parallelMax, setParallelMax] = useState(128)
  const [activeTask, setActiveTask] = useState<'rule' | 'llm' | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (processingProgress >= 100 && processingProgress !== 0) {
      if (processingResetTimer.current) clearTimeout(processingResetTimer.current)
      processingResetTimer.current = setTimeout(() => {
        completedBlocksRef.current = 0
        processingResetTimer.current = null
        setProcessingProgress(0)
      }, 1200)
    }
  }, [processingProgress])

  useEffect(() => () => {
    if (processingResetTimer.current) {
      clearTimeout(processingResetTimer.current)
      processingResetTimer.current = null
    }
  }, [])

  // 获取可用模型列表
  useEffect(() => {
    async function fetchCatalog() {
      try {
        console.log("开始获取模型目录...");
        const res = await axios.get('/api/process/catalog');
        console.log("模型目录获取成功:", res.data);
        const data = res.data as { providers?: LLMProvider[]; defaults?: LLMDefaults };
        const providers = data.providers || [];
        const defaults = data.defaults || {};
        setProviderCatalog(providers);
        const initialModels: Record<string, LLMModel[]> = {}
        providers.forEach(p => {
          if (p.models?.length) initialModels[p.provider] = p.models
        })
        if (Object.keys(initialModels).length) {
          setModelOptions(initialModels)
        }
        const firstProvider = defaults.provider || providers[0]?.provider || ''
        setSelectedProvider(firstProvider)
        const current = providers.find(p => p.provider === firstProvider)
        const initialList = initialModels[firstProvider] || current?.models || []
        const defaultModel = defaults.model || current?.default_model || initialList?.[0]?.id || ''
        setSelectedModel(defaultModel)
    setTemperature(defaults.temperature ?? 0.3)
    const prompt = defaults.system_prompt ?? ''
    setSystemPrompt(prompt)
    setDefaultSystemPrompt(prompt)
    const resolvedMaxParallel = Math.max(1, defaults.parallel_max ?? 32) // 默认值32
    setParallelMax(resolvedMaxParallel)
    const fallbackParallel = Math.max(1, Math.min(8, Math.floor(resolvedMaxParallel / 4))) // 更保守的默认值
    const initialParallel = defaults.parallel ?? defaults.parallelism ?? fallbackParallel
    setParallelism(Math.min(resolvedMaxParallel, Math.max(1, initialParallel)))
      } catch (error: any) {
        console.error("获取模型列表失败:", error);
        addToast('error', '获取模型列表失败，将使用后端默认配置');
      } finally {
        setCatalogLoaded(true);
      }
    }

    fetchCatalog()
  }, [])

  const fetchProviderModels = useCallback(async (provider: string, options?: { force?: boolean }) => {
    if (!provider) return;
    if (!options?.force && modelOptions[provider]) return;
    
    console.log(`获取提供商 ${provider} 的模型列表${options?.force ? '(强制刷新)' : ''}`);
    setModelLoading(true);
    try {
      const params = options?.force ? { refresh: true } : undefined;
      const res = await axios.get(`/api/process/catalog/${provider}`, { params });
      console.log(`成功获取 ${provider} 提供商模型:`, res.data);
      
      const data = res.data as { models?: LLMModel[]; default_model?: string }
      const models = data.models || []
      setModelOptions(prev => ({ ...prev, [provider]: models }))
      setProviderCatalog(prev => prev.map(p => p.provider === provider ? ({ ...p, models }) : p))
      setSelectedModel(prev => {
        if (prev && models.some(m => m.id === prev)) return prev
        if (!models.length) return ''
        return data.default_model || models[0].id
      })
    } catch (error: any) {
      console.error(`获取 ${provider} 模型列表失败:`, error);
      addToast('error', `刷新模型列表失败: ${error?.response?.data?.detail || error?.message || error}`);
      setModelOptions(prev => (prev[provider] ? prev : { ...prev, [provider]: [] }))
    } finally {
      setModelLoading(false);
    }
  }, [modelOptions])

  const availableModels = useMemo(() => {
    if (!selectedProvider) return [] as LLMModel[]
    return modelOptions[selectedProvider] || providerCatalog.find(p => p.provider === selectedProvider)?.models || []
  }, [modelOptions, providerCatalog, selectedProvider])

  useEffect(() => {
    if (!selectedProvider) return
    const provider = providerCatalog.find(p => p.provider === selectedProvider)
    if (!availableModels.length) {
  if (!(selectedProvider in modelOptions)) {
        void fetchProviderModels(selectedProvider)
      } else {
        setSelectedModel('')
      }
      return
    }
    const exists = availableModels.some(m => m.id === selectedModel)
    if (!exists) {
      const next = provider?.default_model || availableModels[0]?.id || ''
      setSelectedModel(next)
    }
  }, [selectedProvider, providerCatalog, availableModels, selectedModel, fetchProviderModels, modelOptions])

  const providerLabel = useMemo(() => {
    if (!catalogLoaded && !providerCatalog.length) return '加载模型…'
    const provider = providerCatalog.find(p => p.provider === selectedProvider)
    return provider?.label || (selectedProvider ? selectedProvider.toUpperCase() : '默认模型')
  }, [catalogLoaded, providerCatalog, selectedProvider])

  const modelLabel = useMemo(() => {
    if (!catalogLoaded && !providerCatalog.length) return '等待配置'
    if (modelLoading && !availableModels.length) return '加载模型…'
    if (!availableModels.length) return selectedModel || '默认'
    const model = availableModels.find(m => m.id === selectedModel)
    return model?.label || selectedModel || '默认'
  }, [catalogLoaded, providerCatalog, availableModels, selectedModel, modelLoading])

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
      const derivedSpeakers = Array.from(
        new Set((res.data?.blocks || []).map((b: Block) => (b.speaker || '').trim()).filter(Boolean))
      ).slice(0, MAX_SPEAKERS) as string[]
      setSpeakers(derivedSpeakers)
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
    if (!doc || loading) return
    
    // 处理说话人列表，确保格式正确且非空
    const speakerList = speakers
      .map(s => s.trim())
      .filter(Boolean);
      
    // 调试信息
    console.log("发送给后端的说话人列表:", speakerList);
    
    setLoading(true)
    setActiveTask('rule')
    try {
      // 添加标准说话人至请求中
      const rule = await axios.post('/api/process', { 
        mode: 'rule', 
        blocks: doc.blocks, 
        speakers: speakerList  // 确保此参数正确传递
      })
      
      // 显示处理结果
      console.log("规则处理完成，检查是否有同音字替换");
      setProcessed(rule.data as Doc)
      setTab('processed')
      setMd(await renderMarkdown(rule.data as Doc, 'processed'))
      addToast('success', '规则处理完成')
    } catch (e: any) {
      addToast('error', '规则处理失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
      setActiveTask(null)
    }
  }

  async function onLLMProcess() {
    if (!doc || loading) return
    
    // 优先使用已经规范化处理过的文本，若没有则使用原始文本
    const sourceDoc = processed || doc;
    
    const speakerList = speakers.map(s => s.trim()).filter(Boolean)
    
    // 添加OpenAI提供商的安全限制
    let safeParallelism = parallelism;
    if (selectedProvider.toLowerCase() === 'openai') {
      const suggestedMax = Math.min(5, parallelMax);
      if (parallelism > suggestedMax) {
        safeParallelism = suggestedMax;
        addToast('info', `OpenAI有速率限制，已自动降低并行度至${suggestedMax}以避免错误`);
      }
    }
    
    const llmPayload = {
      blocks: sourceDoc.blocks, // 使用已处理的文本或原始文本
      provider: selectedProvider || undefined,
      model: selectedModel || undefined,
      temperature,
      system_prompt: systemPrompt.trim() ? systemPrompt.trim() : undefined,
      parallel: safeParallelism,
      speakers: speakerList,
    }
    
    // 添加提示信息，告知用户当前处理的是哪个阶段的文本
    if (processed) {
      addToast('info', '正在对已规范化的文本进行LLM优化');
    } else {
      addToast('info', '未发现规范化文本，直接对原始文本进行LLM优化');
    }
    
    completedBlocksRef.current = 0
    setProcessingProgress(sourceDoc.blocks?.length ? 5 : 0)
    setLoading(true)
    setActiveTask('llm')
    
    try {
      await processStream(llmPayload)
    } catch (e: any) {
      // 如果是主动中止，则不尝试非流式处理
      if (e.name === 'AbortError') {
        addToast('info', '已终止LLM处理')
        setProcessingProgress(0)
      } else {
        completedBlocksRef.current = 0
        setProcessingProgress(5)
        addToast('error', '流式处理失败，尝试改用非流式处理: ' + (e?.message || e))
        try {
          const resp = await axios.post('/api/process', { ...llmPayload, mode: 'llm' })
          const llmDoc = resp.data as Doc
          setProcessed(llmDoc)
          setTab('processed')
          setMd(await renderMarkdown(llmDoc, 'processed'))
          setProcessingProgress(100)
          addToast('success', '已使用非流式 LLM 完成处理')
        } catch (llmError: any) {
          setProcessingProgress(5)
          addToast('error', 'LLM处理失败: ' + (llmError?.message || llmError))
          setTab('processed')
        }
      }
    } finally {
      setLoading(false)
      setActiveTask(null)
      abortControllerRef.current = null
    }
  }

  function abortLLMProcess() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      addToast('info', '正在终止处理...');
    }
  }

  async function processStream(llmPayload: { blocks: Block[]; provider?: string; model?: string; temperature: number; system_prompt?: string; parallel?: number }) {
    if (!llmPayload.blocks?.length) return
    const base = { blocks: llmPayload.blocks.map(b => ({ ...b, content: '', processed: false })) }
    setProcessed(base)
    setTab('processed')

    const totalBlocks = base.blocks.length
    if (!totalBlocks) {
      completedBlocksRef.current = 0
      setProcessingProgress(0)
      return
    }

    completedBlocksRef.current = 0
    setProcessingProgress(5)

    // 创建新的AbortController
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;

    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
    try {
      const res = await fetch('/api/process/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(llmPayload),
        signal  // 传递signal，允许请求中止
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `流式请求失败: ${res.status}`)
      }
      if (!res.body) throw new Error('无响应体')

      reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const applyDelta = (id: string, text: string) => {
        setProcessed(prev => {
          if (!prev) return prev
          const blocks = prev.blocks.map(b => b.id === id ? ({ ...b, content: (b.content || '') + text }) : b)
          return { blocks }
        })
      }

      const markEnd = (id: string, text: string) => {
        completedBlocksRef.current = Math.min(totalBlocks, completedBlocksRef.current + 1)
        const percent = Math.round((completedBlocksRef.current / totalBlocks) * 100)
        setProcessed(prev => {
          if (!prev) return prev
          const blocks = prev.blocks.map(b => b.id === id ? ({ ...b, content: text || b.content, processed: true }) : b)
          return { blocks }
        })
        setProcessingProgress(percent)
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

      setProcessingProgress(100)
      addToast('success', '流式处理完成')
    } catch (error) {
      completedBlocksRef.current = 0
      setProcessingProgress(0)
      throw error
    } finally {
      if (reader) {
        try { reader.releaseLock() } catch {}
      }
    }
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
    const isLikelySpeaker = (value: string) => {
      if (!value) return false
      const hasLetter = /[\u4e00-\u9fa5A-Za-z]/.test(value)
      if (!hasLetter) return false
      const looksLikeDate = /^\d{2,4}\s*[年/-]/.test(value) || /[年月日]\s*\d{1,2}$/.test(value)
      return !looksLikeDate
    }
    const isLikelyTimestamp = (value: string) => {
      if (!value) return false
      return /\d{1,2}:\d{2}(?::\d{2})?/.test(value)
    }
    const visibleBlocks = blocks.filter(b => {
      const speaker = typeof b.speaker === 'string' ? b.speaker.trim() : ''
      const timestamp = typeof b.timestamp === 'string' ? b.timestamp.trim() : ''
      return isLikelySpeaker(speaker) && isLikelyTimestamp(timestamp)
    })
    if (!visibleBlocks.length) return (<div className="preview markdown"><em>暂无内容，请上传文件</em></div>)
    return (
      <div className="preview markdown">
        {visibleBlocks.map((b, idx) => {
          const speaker = (typeof b.speaker === 'string' ? b.speaker.trim() : '')
          const timestamp = (typeof b.timestamp === 'string' ? b.timestamp.trim() : '')
          const header = speaker
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

  const MAX_SPEAKERS = 10

  function addSpeakerField() {
    setSpeakers(prev => (prev.length >= MAX_SPEAKERS ? prev : [...prev, '']))
  }

  function updateSpeakerField(index: number, value: string) {
    setSpeakers(prev => {
      const next = [...prev]
      next[index] = value
      return next
    })
  }

  function removeSpeakerField(index: number) {
    setSpeakers(prev => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="layout">
      <div className="left">
        <div className="left-header">
          <h1>采访稿处理助手</h1>
        </div>
        <div className="box">
          <label htmlFor="doc-title">文档标题</label>
          <input id="doc-title" type="text" placeholder="可选" value={title} onChange={e => setTitle(e.target.value)} />
        </div>

        <div className="box">
          <div className="box-title">选择采访稿（自动解析，支持 .txt/.md/.doc/.docx）</div>
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
            tabIndex={0}
            aria-label="拖拽或点击选择文件"
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                fileInputRef.current?.click()
              }
            }}
          >
            <div className="dz-icon">📄</div>
            <div className="dz-title">拖拽文件到此处，或点击选择</div>
            <div className="dz-sub">支持 .txt / .md / .doc / .docx</div>
            <input
              ref={fileInputRef}
              type="file"
              id="file-input"
              style={{ display: 'none' }}
              onChange={async e => { const f = e.target.files?.[0] || null; setFile(f); setFileName(f?.name || ''); if (f) { setTitle(baseName(f.name)); await onUpload(f) } }}
            />
          </div>
          {fileName && <div className="fileName">{fileName}（已自动解析）</div>}
        </div>

        <div className="box">
          <div className="box-title">说话人定义（最多 10 个）</div>
          {speakers.length === 0 && <div className="empty">点击下方按钮添加说话人</div>}
          {speakers.map((name, idx) => (
            <div className="row" key={`speaker-${idx}`}>
              <input
                type="text"
                value={name}
                onChange={e => updateSpeakerField(idx, e.target.value)}
                placeholder="说话人姓名"
              />
              <button type="button" onClick={() => removeSpeakerField(idx)}>移除</button>
            </div>
          ))}
          <button type="button" onClick={addSpeakerField} disabled={speakers.length >= MAX_SPEAKERS}>
            添加说话人
          </button>
        </div>

        <div className="box">
          <div className="box-title">处理操作</div>
          <div className="row">
            <button 
              onClick={onProcess} 
              className="primary" 
              disabled={!doc || loading || activeTask !== null}
            >
              基础文本规范化
            </button>
            <small className="processing-hint">
              {processed ? "已完成规范化，可继续进行LLM优化" : "规范化后再进行LLM优化效果更佳"}
            </small>
          </div>
        </div>

      </div>

      <div className="right">
        <div className="toolbar">
          <div className="segmented">
            <button className={tab === 'raw' ? 'active' : ''} onClick={() => onSwitchTab('raw')}>解析结果</button>
            <button className={tab === 'processed' ? 'active' : ''} onClick={() => onSwitchTab('processed')}>处理结果</button>
          </div>
          <div className="llm-summary" aria-live="polite">
            <span className="llm-summary-provider">{providerLabel}</span>
            <span className="llm-summary-divider">·</span>
            <span className="llm-summary-model">{modelLabel}</span>
            <span className="llm-summary-divider">·</span>
            <span className="llm-summary-temp">T={temperature.toFixed(1)}</span>
              <span className="llm-summary-divider">·</span>
              <span className="llm-summary-temp">P={parallelism}</span>
              <span className="llm-summary-divider">·</span>
              <span className="llm-summary-temp">Max={parallelMax}</span>
          </div>
          <div className="right-actions">
            <button onClick={()=> setDiffOpen(true)}>差异</button>
            {processingProgress > 0 && (
              <div
                className="progress-indicator"
                aria-live="polite"
                aria-label={`后台任务进度 ${processingProgress}%`}
                title={`后台任务进度 ${processingProgress}%`}
              >
                {processingProgress}%
              </div>
            )}
            <div className="spinner-wrap">{loading ? <span className="spinner" /> : ''}</div>
          </div>
        </div>
        <div className="right-content">
          <div className="preview-wrap">
            {uploadProgress>0 && <div className="upload-progress"><div className="bar" style={{width: uploadProgress+'%'}}></div></div>}
            {processingProgress > 0 && (
              <progress className="task-progress" value={processingProgress} max={100}>{processingProgress}%</progress>
            )}
            <div key={renderKey} className="fade-in">
              {renderPreviewBlocks()}
            </div>
          </div>
          <aside className="side-panel">
            <div className="box llm-box">
              <label htmlFor="llm-provider">LLM 配置</label>
              <div className="llm-config">
                <div className="field">
                  <span className="field-label">模型提供商</span>
                  <select
                    id="llm-provider"
                    value={selectedProvider}
                    onChange={e => setSelectedProvider(e.target.value)}
                    disabled={!catalogLoaded || !providerCatalog.length}
                  >
                    {!providerCatalog.length && <option value="">后端默认</option>}
                    {providerCatalog.map(p => (
                      <option key={p.provider} value={p.provider}>{p.label}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <span className="field-label">模型</span>
                  <select
                    id="llm-model"
                    value={selectedModel}
                    onChange={e => setSelectedModel(e.target.value)}
                    onFocus={() => { void fetchProviderModels(selectedProvider) }}
                    onClick={() => { void fetchProviderModels(selectedProvider) }}
                    disabled={!catalogLoaded || !providerCatalog.length}
                  >
                    {modelLoading && !availableModels.length && (
                      <option value="" disabled>加载可用模型中…</option>
                    )}
                    {availableModels.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.label}{m.context_window ? ` · ${m.context_window}` : ''}
                      </option>
                    ))}
                    {!modelLoading && !availableModels.length && (
                      <option value="">后端默认</option>
                    )}
                  </select>
                </div>
                <div className="field">
                  <span className="field-label">采样温度 {temperature.toFixed(1)}</span>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    value={temperature}
                    onChange={e => setTemperature(Number(e.target.value))}
                  />
                </div>
                <div className="field">
                  <span className="field-label">并行块数 {parallelism}</span>
                  <input
                    type="range"
                    min={1}
                    max={parallelMax}
                    step={1}
                    value={parallelism}
                    onChange={e => setParallelism(Math.min(parallelMax, Math.max(1, Number(e.target.value))))}
                  />
                </div>
                <div className="field">
                  <span className="field-label">系统提示词</span>
                  <textarea
                    id="llm-prompt"
                    className="llm-prompt"
                    value={systemPrompt}
                    onChange={e => setSystemPrompt(e.target.value)}
                    rows={12}
                    placeholder="可自定义提示词，不填则使用默认规则"
                  />
                  <button
                    type="button"
                    className="link"
                    onClick={() => setSystemPrompt(defaultSystemPrompt)}
                    disabled={!catalogLoaded || systemPrompt.trim() === defaultSystemPrompt.trim()}
                  >
                    恢复默认提示词
                  </button>
                </div>
                <div className="field">
                  {activeTask === 'llm' ? (
                    <button 
                      onClick={abortLLMProcess} 
                      className="warning full-width"
                    >
                      终止LLM处理
                    </button>
                  ) : (
                    <button 
                      onClick={onLLMProcess} 
                      className="primary full-width" 
                      disabled={!doc || loading || activeTask !== null}
                    >
                      {processed ? "LLM语言优化(基于规范化文本)" : "LLM语言优化(基于原始文本)"}
                    </button>
                  )}
                </div>

                <div className="box">
                  <div className="box-title">导出</div>
                  <div className="row">
                    <button onClick={() => onExport('md')} disabled={!canExport}>导出 Markdown</button>
                    <button onClick={() => onExport('docx')} disabled={!canExport}>导出 Word</button>
                    <button onClick={() => onExport('pdf')} disabled={!canExport}>导出 PDF</button>
                  </div>
                </div>

              </div>
            </div>
          </aside>
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
