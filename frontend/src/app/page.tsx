'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { AlertTriangle, FileSearch, Link2, Loader2, SearchCheck, Globe2 } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function HomePage() {
  const [url, setUrl] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const router = useRouter()

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/fact-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'Unable to complete investigation')
      }
      router.push(`/report/${payload.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <div className="mark"><SearchCheck size={26} /></div>
        <p className="eyebrow">AI-assisted public claim investigation</p>
        <h1>TisTru checks posts before they become folklore.</h1>
        <p className="lede">
          Submit a URL. TisTru extracts the artifact context, compresses it into claims, searches independent sources, and returns a scored verdict.
        </p>
        <form className="search-panel" onSubmit={submit}>
          <Link2 className="input-icon" size={20} />
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/post-or-article"
            type="url"
            required
          />
          <button disabled={isLoading}>
            {isLoading ? <Loader2 className="spin" size={18} /> : <FileSearch size={18} />}
            Investigate
          </button>
        </form>
        {error && <div className="error"><AlertTriangle size={18} />{error}</div>}
      </section>

      <section className="process-grid">
        {['Extract post metadata, text, images, and videos', 'Summarize context into checkable claims', 'Search credible independent evidence', 'Score confidence and produce verdict'].map((item, index) => (
          <article className="process-card" key={item}>
            <span>0{index + 1}</span>
            <p>{item}</p>
          </article>
        ))}
      </section>

      <EmptyState isLoading={isLoading} />
    </main>
  )
}

function EmptyState({ isLoading }: { isLoading: boolean }) {
  return (
    <section className="empty-state">
      <div className="radar"><Globe2 size={54} /></div>
      <h2>{isLoading ? 'Investigation running' : 'Ready for a source URL'}</h2>
      <p>{isLoading ? 'The backend is extracting context, searching evidence, and composing a report.' : 'Use a public URL with accessible metadata or article text for best results.'}</p>
    </section>
  )
}
