import { useRef, useState, type DragEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CheckCircle2, Download, FilePlus2, Files, Sparkles, UploadCloud, Wand2, XCircle } from 'lucide-react'
import { api, type ContractInput } from '../api'
import ContractForm, { BLANK } from '../components/ContractForm'
import { ErrorBox, PageHeader, Spinner } from '../components/ui'
import { sourceLabel } from '../format'

type BulkResult = Awaited<ReturnType<typeof api.bulkUpload>>

function DropZone({ multiple, accept, onFiles, children }: { multiple?: boolean; accept: string; onFiles: (f: File[]) => void; children: ReactNode }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const drop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    onFiles(Array.from(e.dataTransfer.files))
  }
  return (
    <div
      className={`dropzone${over ? ' over' : ''}`}
      onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      role="button"
      tabIndex={0}
    >
      {children}
      <input ref={input} type="file" hidden multiple={multiple} accept={accept} onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = '' }} />
    </div>
  )
}

export default function Upload() {
  const [tab, setTab] = useState<'bulk' | 'single'>('bulk')
  return (
    <>
      <PageHeader title="Upload Contracts" subtitle="Add contracts in bulk from PDFs or a spreadsheet, or one at a time." />
      <div className="tabs tabs-page">
        <button className={`tab${tab === 'bulk' ? ' active' : ''}`} onClick={() => setTab('bulk')}><Files size={15} /> Bulk upload</button>
        <button className={`tab${tab === 'single' ? ' active' : ''}`} onClick={() => setTab('single')}><FilePlus2 size={15} /> Single contract</button>
      </div>
      {tab === 'bulk' ? <Bulk /> : <Single />}
    </>
  )
}

function Bulk() {
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<BulkResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sampleMsg, setSampleMsg] = useState<string | null>(null)

  const add = (fs: File[]) => {
    const ok = fs.filter((f) => /\.(pdf|csv)$/i.test(f.name))
    setFiles((prev) => [...prev, ...ok.filter((f) => !prev.some((p) => p.name === f.name && p.size === f.size))].slice(0, 50))
    if (ok.length < fs.length) setError('Only PDF and CSV files are accepted; other files were skipped.')
  }

  const upload = async () => {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.bulkUpload(files))
      setFiles([])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="upload-grid">
      <section className="card">
        <DropZone multiple accept=".pdf,.csv,application/pdf,text/csv" onFiles={add}>
          <UploadCloud size={36} />
          <strong>Drop contract PDFs or a CSV here</strong>
          <span className="muted small">or click to choose files · up to 50 files · 15 MB each</span>
        </DropZone>
        {files.length > 0 && (
          <>
            <ul className="file-list">
              {files.map((f, i) => (
                <li key={i}>
                  <span>{f.name}</span>
                  <span className="muted small">{(f.size / 1024).toFixed(0)} KB</span>
                  <button className="btn btn-icon btn-sm" onClick={() => setFiles(files.filter((_, j) => j !== i))} title="Remove"><XCircle size={15} /></button>
                </li>
              ))}
            </ul>
            <button className="btn btn-primary btn-block" onClick={upload} disabled={busy}>
              {busy ? <Spinner label={`Reading ${files.length} file(s)…`} /> : <><Sparkles size={16} /> Upload and extract {files.length} file(s)</>}
            </button>
          </>
        )}
        <ErrorBox message={error} />
        {result && (
          <div className="bulk-result">
            <h3>{result.created.length} contract(s) added{result.errors.length ? `, ${result.errors.length} problem(s)` : ''}</h3>
            <ul>
              {result.created.map((c) => (
                <li key={c.id}>
                  <CheckCircle2 size={15} className="ok" /> <Link to={`/contracts?id=${c.id}`}>{c.name}</Link> <span className="muted small">from {c.source}</span>
                  {c.needs_review && <span className="badge status-upcoming">Needs review</span>}
                </li>
              ))}
              {result.errors.map((e, i) => (
                <li key={i}><XCircle size={15} className="bad" /> {e.file}: <span className="muted">{e.error}</span></li>
              ))}
            </ul>
          </div>
        )}
      </section>
      <aside className="card help">
        <h3>How bulk upload works</h3>
        <ol className="steps">
          <li><strong>PDFs:</strong> the extraction agent reads each contract and fills in vendor/client, value, dates, notice period and scope. The PDF is attached to the contract.</li>
          <li><strong>CSV:</strong> one contract per row. Use the template so the columns match.</li>
          <li>Anything the agent could not read is flagged <em>Needs review</em> on the Overview page.</li>
        </ol>
        <button className="btn btn-ghost btn-block" onClick={() => api.downloadTemplate()}><Download size={15} /> Download CSV template</button>
        <hr />
        <h3>Just exploring?</h3>
        <p className="muted small">Load a realistic set of sample contracts for a small business.</p>
        <button
          className="btn btn-ghost btn-block"
          onClick={async () => {
            const r = await api.loadSample()
            setSampleMsg(`${r.created} sample contracts added.`)
          }}
        >
          Load sample contracts
        </button>
        {sampleMsg && <div className="alert alert-info small">{sampleMsg} <Link to="/">View overview →</Link></div>}
      </aside>
    </div>
  )
}

function Single() {
  const navigate = useNavigate()
  const [initial, setInitial] = useState<ContractInput>(BLANK)
  const [file, setFile] = useState<File | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const autofill = async (fs: File[]) => {
    const f = fs[0]
    if (!f) return
    setFile(f)
    setExtracting(true)
    setError(null)
    setNote(null)
    try {
      const { fields, source } = await api.extract(f)
      const clean = Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== null && v !== undefined))
      setInitial({ ...BLANK, ...clean })
      setNote(`Fields pre-filled from ${f.name} (${sourceLabel(source)}). Please check them before saving.`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setExtracting(false)
    }
  }

  return (
    <div className="upload-grid">
      <section className="card">
        <ContractForm
          initial={initial}
          submitLabel="Save contract"
          onSubmit={async (c) => {
            const saved = await api.createContract(c)
            if (file) await api.attachFile(saved.id, file)
            navigate(`/contracts?id=${saved.id}`)
          }}
        />
      </section>
      <aside className="card help">
        <h3><Wand2 size={18} /> Auto-fill from PDF</h3>
        <p className="muted small">Drop a contract PDF and the extraction agent will fill in the form for you. The PDF is attached when you save.</p>
        <DropZone accept=".pdf,application/pdf" onFiles={autofill}>
          {extracting ? <Spinner label="Reading contract…" /> : <><UploadCloud size={28} /><span className="small">{file ? file.name : 'Choose a PDF'}</span></>}
        </DropZone>
        {note && <div className="alert alert-info small">{note}</div>}
        <ErrorBox message={error} />
      </aside>
    </div>
  )
}
