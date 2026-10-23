import { useEffect, useRef } from 'react'
import Editor, { loader, type OnMount } from '@monaco-editor/react'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import 'monaco-editor/esm/vs/basic-languages/yaml/yaml.contribution'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import type { ErreurScript } from '../lib/api'
import { aideMotCle, propositions } from '../lib/completion'

// Monaco servi localement (pas de CDN) : l'application fonctionne hors réseau.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() }
loader.config({ monaco })
// Accès à l’éditeur pour les tests automatisés et le débogage.
;(window as unknown as { monaco: typeof monaco }).monaco = monaco

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Schema = any

let fournisseursInstalles = false
const contexte: { schema: Schema; references: Record<string, string[]> } = { schema: null, references: {} }

function installerFournisseurs() {
  if (fournisseursInstalles) return
  fournisseursInstalles = true
  monaco.languages.registerCompletionItemProvider('yaml', {
    triggerCharacters: [' ', ':', '-', '{', ','],
    provideCompletionItems(model, position) {
      const lignes = model.getLinesContent()
      const mot = model.getWordUntilPosition(position)
      const plage = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: mot.startColumn,
        endColumn: mot.endColumn,
      }
      const props = propositions(contexte.schema, lignes, position.lineNumber - 1, position.column, contexte.references)
      return {
        suggestions: props.map((p) => ({
          label: p.label,
          kind:
            p.genre === 'cle'
              ? monaco.languages.CompletionItemKind.Property
              : p.genre === 'reference'
                ? monaco.languages.CompletionItemKind.Reference
                : monaco.languages.CompletionItemKind.EnumMember,
          insertText: p.insertText,
          documentation: p.documentation,
          range: plage,
        })),
      }
    },
  })
  monaco.languages.registerHoverProvider('yaml', {
    provideHover(model, position) {
      const mot = model.getWordAtPosition(position)
      if (!mot) return null
      const aide = aideMotCle(contexte.schema, model.getLinesContent(), position.lineNumber - 1, mot.word)
      return aide ? { contents: [{ value: `**${mot.word}** — ${aide}` }] } : null
    },
  })
}

export function Editeur({ texte, onChange, erreurs, schema, references, ligneCible }: {
  texte: string
  onChange: (t: string) => void
  erreurs: ErreurScript[]
  schema: Schema
  references: Record<string, string[]>
  ligneCible: number | null
}) {
  const editeurRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null)
  contexte.schema = schema
  contexte.references = references

  const surMontage: OnMount = (ed) => {
    editeurRef.current = ed as unknown as monaco.editor.IStandaloneCodeEditor
    installerFournisseurs()
  }

  useEffect(() => {
    const ed = editeurRef.current
    const model = ed?.getModel()
    if (!model) return
    monaco.editor.setModelMarkers(
      model,
      'retainwall',
      erreurs.map((e) => ({
        startLineNumber: e.ligne ?? 1,
        endLineNumber: e.ligne ?? 1,
        startColumn: 1,
        endColumn: model.getLineMaxColumn(Math.min(e.ligne ?? 1, model.getLineCount())),
        message: e.chemin ? `${e.chemin} : ${e.message}` : e.message,
        severity: e.niveau === 'avertissement' ? monaco.MarkerSeverity.Warning : monaco.MarkerSeverity.Error,
      })),
    )
  }, [erreurs])

  useEffect(() => {
    if (ligneCible && editeurRef.current) {
      editeurRef.current.revealLineInCenter(ligneCible)
      editeurRef.current.setPosition({ lineNumber: ligneCible, column: 1 })
      editeurRef.current.focus()
    }
  }, [ligneCible])

  return (
    <Editor
      height="100%"
      language="yaml"
      value={texte}
      onChange={(v) => onChange(v ?? '')}
      onMount={surMontage}
      options={{
        minimap: { enabled: false },
        fontSize: 13,
        tabSize: 2,
        insertSpaces: true,
        scrollBeyondLastLine: false,
        wordBasedSuggestions: 'off',
        quickSuggestions: { other: true, comments: false, strings: true },
        automaticLayout: true,
      }}
    />
  )
}
