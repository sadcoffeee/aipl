import { useState } from 'react'
import { SHOW_PLOT_TAB } from '../config'
import { Plot } from './Plot'
import { Console } from './Console'
//import { PyRunner } from './pyRunner'

export default function OutputPanel() {
  const [tab, setTab] = useState<'plot' | 'console'>('console')

  // With the plot tab switched off (see config.ts) the panel is just the console.
  const activeTab = SHOW_PLOT_TAB ? tab : 'console'

  return (
    <div className="output-panel">

      {SHOW_PLOT_TAB ? (
        <div className="output-tabs">
          <button
            className={activeTab === 'console' ? 'tab active' : 'tab'}
            onClick={() => setTab('console')}
          >
            Konsol
          </button>

          <button
            className={activeTab === 'plot' ? 'tab active' : 'tab'}
            onClick={() => setTab('plot')}
          >
            Plot
          </button>
        </div>
      ) : (
        <h2 className="output-title">
          <span className="output-title-dot" aria-hidden="true" />
          Konsol
        </h2>
      )}

      <div className="output-tab-content scrollable-panel">

        <div style={{ display: activeTab === 'console' ? 'block' : 'none' }}>
          <Console />
        </div>

        {SHOW_PLOT_TAB && (
          <div style={{ display: activeTab === 'plot' ? 'block' : 'none' }}>
            <Plot />
          </div>
        )}

      </div>

    </div>
  )
}
