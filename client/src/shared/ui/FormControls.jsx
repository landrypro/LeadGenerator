export function Field({ id, label, value, hint, children }) {
  return <div className="field"><div className="field-label">{id ? <label htmlFor={id}>{label}</label> : <span>{label}</span>}{value && <strong>{value}</strong>}</div>{children}{hint && <small>{hint}</small>}</div>
}


export function Toggle({ checked, onChange, title, description, accent }) {
  return <label className={`toggle-row ${accent ? 'accent' : ''}`}><div><strong>{title}</strong><span>{description}</span></div><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><i><b /></i></label>
}
