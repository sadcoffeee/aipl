/**
 * Lesson text is authored as Markdown so that content authors do not have to
 * write HTML. `marked` turns it into HTML.
 * 
 */

import { marked } from 'marked'

marked.setOptions({ breaks: true })

export function Markdown({ source }: { source: string }) {
  const html = marked.parse(source, { async: false }) as string
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
}
