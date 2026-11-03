import { usePy } from '../usePyodide'

export function PyRunner({ code, fileReady = true }: { code: string; fileReady?: boolean }) {
  const { running, run } = usePy()

  return (
    <div className="py-runner">
      <button className="run-button" disabled={running || !fileReady} onClick={() => void run(code)}>
        {running ? 'Kører…' : 'Kør Koden'}
      </button>
      
    </div>
  )
}
