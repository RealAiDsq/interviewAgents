export function escapeHtml(s: string){
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

const whitespaceTest = /\s/
const chineseChar = /[\u4E00-\u9FFF]/
const asciiPunctuation = /[!-/:-@[-`{-~]/
const fullWidthPunctuation = /[\u3000-\u303F\uFF00-\uFF65]/

const isPunctuation = (ch: string) => asciiPunctuation.test(ch) || fullWidthPunctuation.test(ch)

function tokenize(input: string): string[] {
  if (!input) return []
  const tokens: string[] = []
  let buffer = ''

  const pushBuffer = () => {
    if (buffer) {
      tokens.push(buffer)
      buffer = ''
    }
  }

  for (const ch of input) {
    if (whitespaceTest.test(ch)) {
      pushBuffer()
      const last = tokens[tokens.length - 1]
      if (last && whitespaceTest.test(last[last.length - 1] ?? '')) {
        tokens[tokens.length - 1] = last + ch
      } else {
        tokens.push(ch)
      }
      continue
    }
  if (chineseChar.test(ch) || isPunctuation(ch)) {
      pushBuffer()
      tokens.push(ch)
      continue
    }
    buffer += ch
  }
  pushBuffer()
  return tokens
}

function lcsMatrix(a: string[], b: string[]): number[][] {
  const dp: number[][] = Array(a.length + 1).fill(null).map(() => Array(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  return dp
}

// 细粒度 diff：对中英文内容混合优化，按 token 级别高亮增删
export function diffToHtml(a: string, b: string): string {
  if (a === b) return escapeHtml(a)

  const at = tokenize(a)
  const bt = tokenize(b)
  const dp = lcsMatrix(at, bt)

  let i = 0, j = 0
  const out: string[] = []

  while (i < at.length && j < bt.length) {
    if (at[i] === bt[j]) {
      out.push(escapeHtml(at[i]))
      i += 1
      j += 1
      continue
    }

    if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push(`<span class="diff-del">${escapeHtml(at[i])}</span>`)
      i += 1
    } else {
      out.push(`<span class="diff-ins">${escapeHtml(bt[j])}</span>`)
      j += 1
    }
  }

  while (i < at.length) {
    out.push(`<span class="diff-del">${escapeHtml(at[i++])}</span>`)
  }
  while (j < bt.length) {
    out.push(`<span class="diff-ins">${escapeHtml(bt[j++])}</span>`)
  }

  return out.join('')
}

