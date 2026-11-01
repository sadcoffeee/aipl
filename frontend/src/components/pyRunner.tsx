import { usePy } from '../usePyodide'

export function PyRunner({ code, fileReady = true }: { code: string; fileReady?: boolean }) {
  const { running, output, error, run } = usePy()

  return (
    <div className="py-runner">
      <button className="run-button" disabled={running || !fileReady} onClick={() => void run(code)}>
        {running ? 'Kører…' : 'Kør Koden'}
      </button>
      <pre className="py-console">
        {output}
        {error && <div className="py-console-error">{error}</div>}
        {!output && !error && !running && <span className="muted">Dit output vises her!</span>}
      </pre>
    </div>
  )
}
