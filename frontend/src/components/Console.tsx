import { usePy } from "../usePyodide"

export function Console(){
    const {output, error, running, ranOk} = usePy()
    
    return (
        <pre className ="py-console">
            {running && 'Kører koden...\n'}
            {output}
            {error && (<div className="py-console-error">{error}</div>)}
            {/* The code ran fine but printed nothing: say so, or it looks like nothing happened */}
            {!output && !error && !running && ranOk && (<span className="py-console-ok">Koden blev kørt uden problemer.</span>)}
            {!output && !error && !running && !ranOk && (<span className="muted"> Dit output vises her!</span>)}
        </pre>
            
    )
}