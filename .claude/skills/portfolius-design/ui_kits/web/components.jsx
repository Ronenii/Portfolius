/* Portfolius web kit — shared components.
   Babel JSX; all components exposed to window for cross-file use. */

const { useState, useRef, useEffect, useMemo } = React;

/* ---- Icon (Lucide via global) -------------------------------------------- */
function Icon({ name, size = 16, color, style, ...rest }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      window.lucide.createIcons({ icons: window.lucide.icons, nameAttr: 'data-lucide', elements: [ref.current] });
    }
  }, [name, size]);
  return (
    <i ref={ref}
       data-lucide={name}
       style={{ width: size, height: size, color: color, display: 'inline-flex', ...style }}
       {...rest}></i>
  );
}

/* ---- Wordmark ------------------------------------------------------------ */
function Wordmark({ size = 30, color, dotColor }) {
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: size,
      letterSpacing: '-0.02em',
      lineHeight: 1,
      color: color || 'inherit',
      display: 'inline-flex',
      alignItems: 'baseline',
      gap: size * 0.03,
    }}>
      portfolius<span style={{
        display: 'inline-block',
        width: size * 0.11,
        height: size * 0.11,
        borderRadius: '50%',
        background: dotColor || 'var(--accent-500)',
        alignSelf: 'baseline',
        transform: `translateY(${size * -0.025}px)`,
      }}></span>
    </span>
  );
}

/* ---- Button -------------------------------------------------------------- */
function Button({ variant = 'secondary', icon, iconAfter, children, onClick, type = 'button', ...rest }) {
  return (
    <button type={type} className={`btn btn-${variant}`} onClick={onClick} {...rest}>
      {icon && <Icon name={icon} size={14} />}
      {children}
      {iconAfter && <Icon name={iconAfter} size={14} />}
    </button>
  );
}

/* ---- Badge --------------------------------------------------------------- */
function Badge({ variant = 'neutral', children }) {
  return <span className={`badge ${variant}`}>{children}</span>;
}

/* ---- Field --------------------------------------------------------------- */
function Field({ label, help, children, style }) {
  return (
    <div className="field" style={style}>
      {label && <label>{label}</label>}
      {children}
      {help && <div className="field-help">{help}</div>}
    </div>
  );
}

/* ---- Card panel ---------------------------------------------------------- */
function CardPanel({ variant, eyebrow, title, children, style, action }) {
  const cls = `card-panel${variant ? ` ${variant}` : ''}`;
  return (
    <section className={cls} style={style}>
      {(eyebrow || title || action) && (
        <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14, gap: 12 }}>
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h3 className="section-h">{title}</h3>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/* ---- KPI tile ------------------------------------------------------------ */
function KpiTile({ eyebrow, value, delta, deltaDir = 'up', sub, primary }) {
  return (
    <div className={`card-panel${primary ? ' kpi-primary' : ''}`}>
      <div className="eyebrow">{eyebrow}</div>
      <div className={primary ? 'num-xl' : 'num-lg'} style={{ marginTop: 2 }}>{value}</div>
      {delta && (
        <div className={`num ${deltaDir === 'up' ? 'up' : deltaDir === 'down' ? 'down' : ''}`} style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>
          {deltaDir === 'up' ? '↑ ' : deltaDir === 'down' ? '↓ ' : ''}{delta}
        </div>
      )}
      {sub && <div style={{ fontSize: 11, color: 'var(--ink-500)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

/* ---- Donut chart --------------------------------------------------------- */
function Donut({ data, size = 180, thickness = 18, centerTop, centerBottom }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let acc = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="transparent" stroke="var(--paper-200)" strokeWidth={thickness} />
      {data.map((d, i) => {
        const len = (d.value / total) * c;
        const off = -acc;
        acc += len;
        return (
          <circle key={i}
            cx={size/2} cy={size/2} r={r}
            fill="transparent"
            stroke={d.color}
            strokeWidth={thickness}
            strokeDasharray={`${len} ${c - len}`}
            strokeDashoffset={off}
            transform={`rotate(-90 ${size/2} ${size/2})`} />
        );
      })}
      {centerTop && (
        <text x={size/2} y={size/2 - 4} textAnchor="middle"
              fontFamily="JetBrains Mono" fontSize="18" fontWeight="500"
              fill="currentColor">{centerTop}</text>
      )}
      {centerBottom && (
        <text x={size/2} y={size/2 + 14} textAnchor="middle"
              fontFamily="Geist, sans-serif" fontSize="11"
              fill="var(--ink-500)">{centerBottom}</text>
      )}
    </svg>
  );
}

/* ---- Allocation card (donut + legend) ------------------------------------ */
function AllocationCard({ title, eyebrow, data, total, formatVal }) {
  const sum = data.reduce((s, x) => s + x.value, 0);
  return (
    <CardPanel variant="chart" eyebrow={eyebrow} title={title}>
      <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <Donut data={data} size={150} thickness={16} centerTop={total} centerBottom={`${data.length} markets`} />
        <div style={{ flex: 1, minWidth: 200 }}>
          {data.map((d, i) => (
            <div key={i} className="legend-row">
              <span className="dot" style={{ background: d.color }}></span>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.label}</span>
              <span className="pct">{Math.round((d.value / sum) * 100)}%</span>
              <span className="val">{formatVal ? formatVal(d.value) : d.value}</span>
            </div>
          ))}
        </div>
      </div>
    </CardPanel>
  );
}

/* ---- Bars (horizontal small) --------------------------------------------- */
function Bars({ data, max }) {
  const m = max || Math.max(...data.map(d => d.value));
  return (
    <div className="bars">
      {data.map((d, i) => (
        <div key={i} className="bar-row">
          <span style={{ fontSize: 12 }}>{d.label}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(d.value / m) * 100}%` }}></div></div>
          <span className="pct">{Math.round((d.value / data.reduce((s, x) => s + x.value, 0)) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

/* ---- Sidebar ------------------------------------------------------------- */
function Sidebar({ active, onNav }) {
  const nav = [
    { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
    { id: 'holdings',  label: 'Holdings',  icon: 'landmark' },
    { id: 'assistant', label: 'Assistant', icon: 'sparkles' },
  ];
  const foot = [
    { id: 'profile',  label: 'Profile',  icon: 'user-round' },
    { id: 'settings', label: 'Settings', icon: 'settings-2' },
  ];
  return (
    <aside className="sidebar">
      <div className="brand"><Wordmark size={26} /></div>
      <div className="group-label">Workspace</div>
      {nav.map(n => (
        <button key={n.id} className={`nav-item ${active === n.id ? 'active' : ''}`} onClick={() => onNav(n.id)}>
          <Icon name={n.icon} size={16} />{n.label}
        </button>
      ))}
      <div className="sidebar-foot">
        {foot.map(n => (
          <button key={n.id} className={`nav-item ${active === n.id ? 'active' : ''}`} onClick={() => onNav(n.id)}>
            <Icon name={n.icon} size={16} />{n.label}
          </button>
        ))}
      </div>
    </aside>
  );
}

/* ---- Header -------------------------------------------------------------- */
function Header({ title, meta, mode, onModeChange }) {
  return (
    <header className="header">
      <div className="crumbs">
        <span className="ttl">{title}</span>
        {meta && <span className="meta">{meta}</span>}
      </div>
      <div className="header-actions">
        <div className="mode-toggle">
          <button className={mode === 'paper' ? 'on' : ''} onClick={() => onModeChange('paper')}>Paper</button>
          <button className={mode === 'terminal' ? 'on' : ''} onClick={() => onModeChange('terminal')}>Terminal</button>
        </div>
        <span className="avatar">R</span>
      </div>
    </header>
  );
}

Object.assign(window, {
  Icon, Wordmark, Button, Badge, Field, CardPanel, KpiTile,
  Donut, AllocationCard, Bars, Sidebar, Header
});
