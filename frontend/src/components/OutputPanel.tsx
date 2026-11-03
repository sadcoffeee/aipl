import { useState } from 'react'
import { Plot } from './Plot'
import { Console } from './Console'
//import { PyRunner } from './pyRunner'

export default function OutputPanel() {
  const [tab, setTab] = useState<'plot' | 'console'>('console')

   return (
    <div className="output-panel">

      <div className="output-tabs">
        <button
          className={tab === 'console' ? 'tab active' : 'tab'}
          onClick={() => setTab('console')}
        >
          Konsol
        </button>

        <button
          className={tab === 'plot' ? 'tab active' : 'tab'}
          onClick={() => setTab('plot')}
        >
          Plot
        </button>
      </div>

      <div className="output-tab-content scrollable-panel">

        <div style={{ display: tab === 'console' ? 'block' : 'none' }}>
          <Console />
        </div>

        <div style={{ display: tab === 'plot' ? 'block' : 'none' }}>
          <Plot />
        </div>

      </div>

    </div>
  )
}
