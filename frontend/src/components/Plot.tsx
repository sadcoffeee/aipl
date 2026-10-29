import { useEffect, useState } from 'react'
import { usePy } from '../usePyodide'

export function Plot(){
    const { loadFile } = usePy()
    const [ready, setReady] = useState(false)

    useEffect(() => {
        async function prepareFile() {
            await loadFile('/datasets/EKG_data.txt', 'EKG_data.txt')
            setReady(true)
        }
        prepareFile()
    }, [])

    return(
        <div className="ekg-plot">
            {ready ? <p>Filen er klar!</p> : <p>Indlæser fil...</p>}
        </div>
    )
}
