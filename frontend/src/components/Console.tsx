import { usePy } from "../usePyodide"

export function Console(){
    const {output, error, running} = usePy()
    
    return (
        <pre className ="py-console">
            {running && 'Kører koden...\n'}
            {output}
            {error && (<div className="py-console-error">{error}</div>)}
            {!output && !error && !running && (<span className="muted"> Dit output vises her!</span>)}
        </pre>
            
    )
}