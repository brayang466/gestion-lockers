import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getModuleByPath } from '../config/modulesConfig'

function formatCell(value) {
  if (value == null || value === '') return '—'
  if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}/)) {
    return new Date(value).toLocaleDateString('es-ES', { dateStyle: 'short' })
  }
  return String(value)
}

export default function ModuleCrudPage() {
  const { modulePath } = useParams()
  const config = getModuleByPath(modulePath)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({})
  const [saving, setSaving] = useState(false)

  if (!config) {
    return (
      <div className="max-w-7xl mx-auto">
        <p className="text-red-600">Módulo no encontrado.</p>
      </div>
    )
  }

  const { title, apiPath, columns, formFields, hideCreate = false } = config

  const fetchList = () => {
    setLoading(true)
    fetch(apiPath, { credentials: 'same-origin' })
      .then((res) => {
        if (!res.ok) throw new Error('Error al cargar')
        return res.json()
      })
      .then((data) => {
        setItems(Array.isArray(data) ? data : [])
        setError(null)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchList()
  }, [apiPath])

  const openCreate = () => {
    setEditingId(null)
    const initial = {}
    formFields.forEach((f) => {
      initial[f.name] = f.type === 'number' ? '' : ''
    })
    setFormData(initial)
    setModalOpen(true)
  }

  const openEdit = (row) => {
    setEditingId(row.id)
    const initial = {}
    formFields.forEach((f) => {
      let v = row[f.name]
      if (v != null && typeof v === 'string' && v.includes('T') && f.type === 'date') {
        v = v.slice(0, 10)
      }
      initial[f.name] = v ?? ''
    })
    setFormData(initial)
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setEditingId(null)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setSaving(true)
    const payload = {}
    formFields.forEach((f) => {
      let v = formData[f.name]
      if (f.type === 'number' && v !== '') v = Number(v)
      if (v !== '' && v != null) payload[f.name] = v
    })

    const url = editingId ? `${apiPath}/${editingId}` : apiPath
    const method = editingId ? 'PUT' : 'POST'
    fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    })
      .then((res) => {
        if (!res.ok) throw new Error(res.status === 204 ? 'OK' : 'Error al guardar')
        return method === 'PUT' ? res.json() : res.json()
      })
      .then(() => {
        closeModal()
        fetchList()
      })
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false))
  }

  const handleDelete = (id) => {
    if (!window.confirm('¿Eliminar este registro?')) return
    fetch(`${apiPath}/${id}`, { method: 'DELETE', credentials: 'same-origin' })
      .then((res) => {
        if (!res.ok) throw new Error('Error al eliminar')
        fetchList()
      })
      .catch((err) => setError(err.message))
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="text-slate-500 text-sm mt-0.5">Listado y alta/edición de registros</p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-medium rounded-xl shadow-sm transition-colors"
        >
          Crear
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-pulse text-slate-500">Cargando...</div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  {columns.map((col) => (
                    <th key={col.key} className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      {col.label}
                    </th>
                  ))}
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase w-24">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length + 1} className="px-4 py-8 text-center text-slate-500">
                      {hideCreate
                        ? 'No hay registros.'
                        : 'No hay registros. Use "Crear" para agregar uno.'}
                    </td>
                  </tr>
                ) : (
                  items.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/50">
                      {columns.map((col) => (
                        <td key={col.key} className="px-4 py-3 text-sm text-slate-700 whitespace-nowrap max-w-[200px] truncate">
                          {formatCell(row[col.key])}
                        </td>
                      ))}
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => openEdit(row)}
                          className="inline-flex items-center gap-1.5 text-amber-600 hover:text-amber-700 font-medium text-sm mr-3"
                          title="Editar"
                        >
                          <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                          Editar
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(row.id)}
                          className="inline-flex items-center gap-1.5 text-red-600 hover:text-red-700 font-medium text-sm"
                          title="Eliminar"
                        >
                          <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={closeModal}>
          <div
            className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6 border-b border-slate-200">
              <h2 className="text-lg font-semibold text-slate-900">
                {editingId ? 'Editar registro' : 'Nuevo registro'}
              </h2>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {formFields.map((f) => (
                <div key={f.name}>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    {f.label}
                    {f.required && <span className="text-red-500"> *</span>}
                  </label>
                  {f.type === 'textarea' ? (
                    <textarea
                      value={formData[f.name] ?? ''}
                      onChange={(e) => setFormData((d) => ({ ...d, [f.name]: e.target.value }))}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                      rows={3}
                    />
                  ) : f.type === 'select' && Array.isArray(f.options) ? (
                    <select
                      value={formData[f.name] ?? ''}
                      onChange={(e) => setFormData((d) => ({ ...d, [f.name]: e.target.value }))}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500 bg-white"
                      required={f.required}
                    >
                      {f.options.map((opt) => (
                        <option key={opt || '__empty'} value={opt}>
                          {opt === '' ? 'Seleccione…' : opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={f.type === 'date' ? 'date' : f.type === 'number' ? 'number' : 'text'}
                      value={formData[f.name] ?? ''}
                      onChange={(e) => setFormData((d) => ({ ...d, [f.name]: e.target.value }))}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                      required={f.required}
                    />
                  )}
                </div>
              ))}
              <div className="flex gap-3 pt-4">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white font-medium rounded-lg disabled:opacity-50"
                >
                  {saving ? 'Guardando...' : 'Guardar'}
                </button>
                <button type="button" onClick={closeModal} className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
