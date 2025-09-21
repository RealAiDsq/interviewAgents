export function escapeHtml(s: string){
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

// 简易词级 diff（LCS）
export function diffToHtml(a: string, b: string): string {
  const at = a.split(/(\s+)/)
  const bt = b.split(/(\s+)/)
  const dp: number[][] = Array(at.length+1).fill(0).map(()=>Array(bt.length+1).fill(0))
  for (let i=at.length-1;i>=0;i--) {
    for (let j=bt.length-1;j>=0;j--) {
      dp[i][j] = at[i]===bt[j] ? dp[i+1][j+1]+1 : Math.max(dp[i+1][j], dp[i][j+1])
    }
  }
  let i=0,j=0, out: string[]=[]
  while (i<at.length && j<bt.length){
    if (at[i]===bt[j]) { out.push(escapeHtml(at[i])); i++; j++; }
    else if (dp[i+1][j] >= dp[i][j+1]) { out.push(`<span class=\"diff-del\">${escapeHtml(at[i])}</span>`); i++; }
    else { out.push(`<span class=\"diff-ins\">${escapeHtml(bt[j])}</span>`); j++; }
  }
  while (i<at.length) { out.push(`<span class=\"diff-del\">${escapeHtml(at[i++])}</span>`)}
  while (j<bt.length) { out.push(`<span class=\"diff-ins\">${escapeHtml(bt[j++])}</span>`)}
  return out.join('')
}

