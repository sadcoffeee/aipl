import { usePy } from '../usePyodide'

export function PyRunner({ code }: { code: string }) {
  const { running, output, error, run } = usePy()

  return (
    <div className="py-runner">
      <button className="run-button" disabled={running} onClick={() => void run(code)}>
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
