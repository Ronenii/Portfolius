/* Portfolius web kit — screens (Dashboard, Holdings, Assistant, Profile). */

const { useState: useStateS } = React;

/* ---- Mock data ----------------------------------------------------------- */
const MOCK_HOLDINGS = [
  { id: 1, ticker: 'VTI',  name: 'Vanguard Total Stock Market ETF',  cls: 'ETF',   region: 'US',     shares: 8124, price: 30.58, avg: 25.42, day: 2.41 },
  { id: 2, ticker: 'VXUS', name: 'Vanguard Total International Stock', cls: 'ETF', region: 'World ex-US', shares: 1402, price: 60.06, avg: 54.10, day: 0.62 },
  { id: 3, ticker: 'BND',  name: 'Vanguard Total Bond Market ETF',   cls: 'Bond',  region: 'US',     shares: 411,  price: 75.45, avg: 78.20, day: -0.18 },
  { id: 4, ticker: 'VWO',  name: 'Vanguard FTSE Emerging Markets',   cls: 'ETF',   region: 'EM',     shares: 240,  price: 47.20, avg: 42.10, day: 1.12 },
  { id: 5, ticker: 'VPL',  name: 'Vanguard FTSE Pacific',            cls: 'ETF',   region: 'APAC',   shares: 180,  price: 78.40, avg: 70.20, day: 0.34 },
  { id: 6, ticker: 'VGK',  name: 'Vanguard FTSE Europe',             cls: 'ETF',   region: 'Europe', shares: 320,  price: 70.10, avg: 62.40, day: 0.81 },
  { id: 7, ticker: 'GLD',  name: 'SPDR Gold Shares',                 cls: 'Commodity', region: 'Global', shares: 48,  price: 220.40, avg: 180.00, day: -0.42 },
  { id: 8, ticker: 'VNQ',  name: 'Vanguard Real Estate ETF',         cls: 'REIT',  region: 'US',     shares: 92,  price: 92.10, avg: 85.20, day: 0.21 },
];

const REGION_DATA = [
  { label: 'United States',  value: 152800, color: '#1F6B6E' },   /* accent — teal */
  { label: 'Europe',         value: 79900,  color: '#4F7A4A' },   /* gain */
  { label: 'Asia Pacific',   value: 50700,  color: '#4A6E8C' },   /* info */
  { label: 'Emerging mkts',  value: 43400,  color: '#71A8AB' },   /* accent-300 */
  { label: 'Other / global', value: 36800,  color: '#6E6757' },   /* ink-500 */
];

const SECTOR_DATA = [
  { label: 'Technology',  value: 38 },
  { label: 'Financials',  value: 18 },
  { label: 'Healthcare',  value: 14 },
  { label: 'Industrials', value: 12 },
  { label: 'Consumer',    value: 10 },
  { label: 'Energy',      value:  8 },
];

const fmt = n => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtShort = n => '$' + Math.round(n).toLocaleString('en-US');
const fmtK = n => '$' + (Math.round(n / 100) / 10).toFixed(1) + 'k';

/* ---- Dashboard ----------------------------------------------------------- */
function DashboardScreen() {
  const total = MOCK_HOLDINGS.reduce((s, h) => s + h.shares * h.price, 0);
  const cost  = MOCK_HOLDINGS.reduce((s, h) => s + h.shares * h.avg, 0);
  const dayDelta = total * 0.0067;
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Your portfolio</h1>
          <div className="sub">As of May 27, 2026 · daily close 14:32 UTC</div>
        </div>
        <div className="row-flex">
          <Button variant="secondary" icon="sliders-horizontal">Filters</Button>
          <Button variant="primary" icon="plus">Add holding</Button>
        </div>
      </header>

      <div className="grid-3">
        <KpiTile primary eyebrow="Portfolio value"    value={fmt(total)}             delta={fmt(dayDelta) + ' today · 0.67%'} deltaDir="up" />
        <KpiTile         eyebrow="All-time return"    value={'+' + fmtShort(total - cost)} delta={`${((total/cost - 1) * 100).toFixed(1)}% · since Jan 2023`} deltaDir="up" />
        <KpiTile         eyebrow="Next contribution"  value="$1,500" sub="Jun 1 · monthly · into VXUS" />
      </div>

      <div className="grid-dash">
        <AllocationCard
          eyebrow="Allocation"
          title="By region"
          data={REGION_DATA}
          total={fmtK(total)}
          formatVal={fmtShort}
        />
        <CardPanel eyebrow="Allocation" title="By sector">
          <Bars data={SECTOR_DATA} />
        </CardPanel>
      </div>

      <CardPanel
        eyebrow="Top holdings"
        title="By value"
        action={<Button variant="ghost" iconAfter="arrow-up-right">View all holdings</Button>}
      >
        <table className="tbl">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>Class</th>
              <th className="right">Shares</th>
              <th className="right">Value</th>
              <th className="right">Δ today</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_HOLDINGS.slice(0, 5).map(h => (
              <tr key={h.id}>
                <td className="ticker">{h.ticker}</td>
                <td>{h.name}</td>
                <td><Badge variant={h.cls === 'Bond' ? 'neutral' : h.cls === 'Commodity' ? 'brass' : 'neutral'}>{h.cls}</Badge></td>
                <td className="right num">{h.shares.toLocaleString()}</td>
                <td className="right num">{fmt(h.shares * h.price)}</td>
                <td className={`right num ${h.day >= 0 ? 'up' : 'down'}`}>{h.day >= 0 ? '↑' : '↓'} {Math.abs(h.day).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardPanel>
    </div>
  );
}

/* ---- Holdings ------------------------------------------------------------ */
function HoldingsScreen() {
  const [filter, setFilter] = useStateS('all');
  const [selected, setSelected] = useStateS(null);
  const filtered = filter === 'all' ? MOCK_HOLDINGS : MOCK_HOLDINGS.filter(h => h.cls === filter);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Holdings</h1>
          <div className="sub">{MOCK_HOLDINGS.length} positions · daily close prices</div>
        </div>
        <div className="row-flex">
          <Button variant="secondary" icon="arrow-up-down">Sort: value</Button>
          <Button variant="primary" icon="plus">Add holding</Button>
        </div>
      </header>

      <div className="row-flex">
        {['all', 'ETF', 'Bond', 'REIT', 'Commodity'].map(f => (
          <button key={f}
                  className={`pill ${filter === f ? 'active' : ''}`}
                  onClick={() => setFilter(f)}>
            {f === 'all' ? 'All' : f}
          </button>
        ))}
      </div>

      <CardPanel style={{ padding: 0, overflow: 'hidden' }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Name</th>
              <th>Class</th>
              <th>Region</th>
              <th className="right">Shares</th>
              <th className="right">Avg cost</th>
              <th className="right">Price</th>
              <th className="right">Value</th>
              <th className="right">Δ today</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(h => (
              <tr key={h.id}
                  className={selected === h.id ? 'selected' : ''}
                  onClick={() => setSelected(h.id === selected ? null : h.id)}
                  style={{ cursor: 'pointer' }}>
                <td className="ticker">{h.ticker}</td>
                <td>{h.name}</td>
                <td><Badge variant={h.cls === 'Commodity' ? 'brass' : 'neutral'}>{h.cls}</Badge></td>
                <td style={{ color: 'var(--ink-500)' }}>{h.region}</td>
                <td className="right num">{h.shares.toLocaleString()}</td>
                <td className="right num" style={{ color: 'var(--ink-500)' }}>{fmt(h.avg)}</td>
                <td className="right num">{fmt(h.price)}</td>
                <td className="right num" style={{ fontWeight: 500 }}>{fmt(h.shares * h.price)}</td>
                <td className={`right num ${h.day >= 0 ? 'up' : 'down'}`}>{h.day >= 0 ? '↑' : '↓'} {Math.abs(h.day).toFixed(2)}%</td>
                <td>
                  <button className="btn btn-ghost" style={{ padding: 4 }} onClick={e => e.stopPropagation()}>
                    <Icon name="pencil" size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardPanel>

      {selected !== null && (
        <CardPanel eyebrow="Selected" title={MOCK_HOLDINGS.find(h => h.id === selected).name}
                   action={<Button variant="ghost" icon="trash-2">Remove</Button>}>
          <div className="grid-3">
            {(() => {
              const h = MOCK_HOLDINGS.find(x => x.id === selected);
              const value = h.shares * h.price;
              const gain  = (h.price - h.avg) * h.shares;
              const gainPct = ((h.price / h.avg) - 1) * 100;
              return (<>
                <KpiTile eyebrow="Market value" value={fmt(value)} />
                <KpiTile eyebrow="Unrealized P&amp;L" value={(gain >= 0 ? '+' : '') + fmtShort(gain)} delta={gainPct.toFixed(1) + '%'} deltaDir={gain >= 0 ? 'up' : 'down'} />
                <KpiTile eyebrow="Weight in portfolio" value={(value / MOCK_HOLDINGS.reduce((s, x) => s + x.shares * x.price, 0) * 100).toFixed(1) + '%'} />
              </>);
            })()}
          </div>
        </CardPanel>
      )}
    </div>
  );
}

/* ---- Assistant ----------------------------------------------------------- */
const SEED_MESSAGES = [
  { from: 'ai', text: ['Your US exposure is at ', { num: '68%' }, ' against your ', { num: '60%' }, ' target. Asia Pacific and emerging markets are both within ', { num: '1 point' }, ' of target. Want me to draft the next contribution?'] },
];
const SUGGESTIONS = [
  'What should I buy next to hit my target allocation?',
  'How concentrated am I in tech?',
  'Project portfolio value in 10 years at current contributions.',
];
const SCRIPTED_REPLIES = {
  next: ['Routing your next ', { num: '$1,500' }, ' into ', { tk: 'VXUS' }, ' would close ', { num: '~1.4 pts' }, ' of the US-overweight gap. After: US ', { num: '66.6%' }, ', World ex-US ', { num: '21.4%' }, '.'],
  tech: [{ tk: 'VTI' }, ' and ', { tk: 'VGK' }, ' together give you ', { num: '38%' }, ' technology exposure — roughly equal to a global market-cap weight. Not concentrated, but worth watching.'],
  project: ['At ', { num: '$1,500' }, '/mo and a ', { num: '7%' }, ' real return, your portfolio reaches ', { num: '~$1.06M' }, ' in ten years. This is illustrative, not advice.'],
};

function renderRich(parts) {
  if (typeof parts === 'string') return parts;
  return parts.map((p, i) => {
    if (typeof p === 'string') return <React.Fragment key={i}>{p}</React.Fragment>;
    if (p.num) return <span key={i} className="num">{p.num}</span>;
    if (p.tk)  return <span key={i} className="ticker"><b>{p.tk}</b></span>;
    return null;
  });
}

function AssistantScreen() {
  const [messages, setMessages] = useStateS(SEED_MESSAGES);
  const [input, setInput] = useStateS('');

  function send(text) {
    const next = [...messages, { from: 'user', text }];
    let reply = ['Let me sit with that. In short: stay the course; the next contribution does most of the work.'];
    const t = text.toLowerCase();
    if (t.includes('buy') || t.includes('next') || t.includes('allocation')) reply = SCRIPTED_REPLIES.next;
    else if (t.includes('tech') || t.includes('concentr')) reply = SCRIPTED_REPLIES.tech;
    else if (t.includes('project') || t.includes('year') || t.includes('value')) reply = SCRIPTED_REPLIES.project;
    next.push({ from: 'ai', text: reply });
    setMessages(next);
    setInput('');
  }

  return (
    <div className="page reading">
      <header className="page-head">
        <div>
          <h1>Assistant</h1>
          <div className="sub">Grounded in your profile and current holdings · educational only</div>
        </div>
      </header>

      <div className="context-strip">
        <b>Context:</b>&nbsp; 8 holdings · 5 regions · 3 currencies · profile: long-horizon, monthly contributions · base USD
      </div>

      <CardPanel variant="chart">
        <div className="chat">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.from}`}>{renderRich(m.text)}</div>
          ))}
        </div>
      </CardPanel>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {SUGGESTIONS.map((s, i) => (
          <button key={i} className="pill" onClick={() => send(s)}>{s}</button>
        ))}
      </div>

      <div className="composer">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about your portfolio…"
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (input.trim()) send(input.trim()); } }}
        />
        <Button variant="primary" icon="sparkles" onClick={() => input.trim() && send(input.trim())}>Send</Button>
      </div>

      <p className="lede" style={{ fontSize: 14, color: 'var(--ink-500)', marginTop: 8 }}>
        Educational observations only. The assistant cannot place trades and is not a substitute for a licensed advisor.
      </p>
    </div>
  );
}

/* ---- Profile ------------------------------------------------------------- */
function ProfileScreen() {
  const [profile, setProfile] = useStateS({
    name: 'Ronen', goal: 'Retire by 60. Buy ETFs monthly.',
    horizon: 28, frequency: 'monthly', currency: 'USD',
    markets: ['US', 'Europe', 'APAC', 'EM'],
  });
  const set = (k, v) => setProfile(p => ({ ...p, [k]: v }));
  const toggleMarket = m => set('markets', profile.markets.includes(m) ? profile.markets.filter(x => x !== m) : [...profile.markets, m]);

  return (
    <div className="page reading">
      <header className="page-head">
        <div>
          <h1>Your profile</h1>
          <div className="sub">Set once. Powers your dashboard and the assistant's grounding.</div>
        </div>
      </header>

      <CardPanel eyebrow="Identity" title="Who's investing">
        <div className="col-flex">
          <Field label="Display name">
            <input type="text" value={profile.name} onChange={e => set('name', e.target.value)} />
          </Field>
          <Field label="Long-term goal" help="One sentence. The assistant reads this verbatim.">
            <textarea rows="2" value={profile.goal} onChange={e => set('goal', e.target.value)}
                      style={{ fontFamily: 'inherit', fontSize: 14, padding: '8px 10px', borderRadius: 6, border: '1px solid var(--rule)', background: 'var(--paper-50)', color: 'inherit', resize: 'vertical' }} />
          </Field>
        </div>
      </CardPanel>

      <CardPanel eyebrow="Plan" title="How you invest">
        <div className="grid-3">
          <Field label="Time horizon (years)" help="At least 3 years.">
            <input className="num" type="number" min="3" value={profile.horizon} onChange={e => set('horizon', e.target.value)} />
          </Field>
          <Field label="Frequency">
            <select value={profile.frequency} onChange={e => set('frequency', e.target.value)}>
              <option>weekly</option>
              <option>monthly</option>
              <option>quarterly</option>
              <option>ad-hoc</option>
            </select>
          </Field>
          <Field label="Base currency">
            <select value={profile.currency} onChange={e => set('currency', e.target.value)}>
              <option>USD</option><option>EUR</option><option>GBP</option><option>ILS</option><option>JPY</option>
            </select>
          </Field>
        </div>
      </CardPanel>

      <CardPanel eyebrow="Scope" title="Markets of interest" action={<span className="field-help">{profile.markets.length} selected</span>}>
        <div className="row-flex" style={{ flexWrap: 'wrap' }}>
          {['US', 'Europe', 'APAC', 'EM', 'Israel', 'Global'].map(m => (
            <button key={m} className={`pill ${profile.markets.includes(m) ? 'active' : ''}`} onClick={() => toggleMarket(m)}>
              {m}
            </button>
          ))}
        </div>
      </CardPanel>

      <div className="row-flex" style={{ justifyContent: 'flex-end' }}>
        <Button variant="ghost">Discard</Button>
        <Button variant="primary" icon="check">Save profile</Button>
      </div>
    </div>
  );
}

Object.assign(window, { DashboardScreen, HoldingsScreen, AssistantScreen, ProfileScreen });
