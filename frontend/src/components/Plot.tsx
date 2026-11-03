import { usePy } from '../usePyodide'

export function Plot(){
    const { image, error, running } = usePy()

    return(
        <div className="ekg-plot scrollable-panel">
            {running && <p>Kører koden...</p>}
            {error && <p>Der opstod en fejl: {error}</p>}
            {!running && !error && !image && <p className="muted">Kør koden for at se grafen.</p>}
            {image && <img src={`data:image/png;base64,${image}`} alt="EKG plot" />}
        </div>
    )
} 
