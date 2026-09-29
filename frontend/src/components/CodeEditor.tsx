import { python } from '@codemirror/lang-python'
import type { Extension } from '@codemirror/state'
import CodeMirror from '@uiw/react-codemirror'

export default function CodeEditor({
  value,
  onChange,
  editable = true,
  extensions = [],
}: {
  value: string
  onChange?: (value: string) => void
  editable?: boolean
  extensions?: Extension[]
}) {
  return (
    <CodeMirror
      value={value}
      height="320px"
      editable={editable}
      extensions={[python(), ...extensions]}
      onChange={onChange}
      basicSetup={{
        autocompletion: false,
        foldGutter: false,
        lineNumbers: true,
        highlightActiveLine: editable,
        highlightActiveLineGutter: editable,
      }}
    />
  )
}
