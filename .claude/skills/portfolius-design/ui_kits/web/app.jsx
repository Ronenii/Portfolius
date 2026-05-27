/* Portfolius web kit — app host with accent-palette tweaks. */

const { useState: useStateA, useEffect: useEffectA } = React;

const ACCENT_PALETTES = /*EDITMODE-BEGIN*/{
  "accent": "teal"
}/*EDITMODE-END*/;

const PALETTE_DEFS = {
  teal:   { 500: '#1F6B6E', 700: '#114448', 300: '#71A8AB', 100: '#D3E6E7', 900: '#0A2D30',
            label: 'Teal',  blurb: 'Money green · calm · default' },
  forest: { 500: '#2C6E4D', 700: '#194A30', 300: '#7BB098', 100: '#D6E7DD', 900: '#0E3022',
            label: 'Forest', blurb: 'Warmer green · evergreen' },
  brass:  { 500: '#A87B2C', 700: '#7E5A1D', 300: '#D4B36A', 100: '#F0E0B6', 900: '#5A4014',
            label: 'Brass', blurb: 'Warm metal · classical' },
  sky:    { 500: '#4A8AB0', 700: '#2E5F7D', 300: '#A5C9DD', 100: '#DEEBF3', 900: '#1A3A50',
            label: 'Sky',   blurb: 'Pale aqua · open, fresh' },
  ink:    { 500: '#2A4A7F', 700: '#1A3460', 300: '#7B95C2', 100: '#DDE3EE', 900: '#0F2350',
            label: 'Ink',   blurb: 'Fountain pen blue' },
  claret: { 500: '#7A2E3A', 700: '#5A1E29', 300: '#BB8089', 100: '#ECD7DA', 900: '#3C0E16',
            label: 'Claret', blurb: 'Oxblood · leather' },
  slate:  { 500: '#3B414A', 700: '#252A33', 300: '#8A8F98', 100: '#DCDEE3', 900: '#13161B',
            label: 'Slate',  blurb: 'No accent · mono' },
};

function paletteToStyle(p) {
  return {
    '--accent-500': p[500],
    '--accent-700': p[700],
    '--accent-300': p[300],
    '--accent-100': p[100],
    '--accent-900': p[900],
  };
}

function App() {
  const [t, setTweak] = useTweaks(ACCENT_PALETTES);
  const [route, setRoute] = useStateA('dashboard');
  const [mode, setMode]   = useStateA('paper');

  useEffectA(() => {
    if (window.lucide) window.lucide.createIcons();
  }, [route, mode, t.accent]);

  const headerFor = {
    dashboard: { title: 'Dashboard', meta: '// 2026.05.27 · 14:32 utc' },
    holdings:  { title: 'Holdings',  meta: '// 8 positions' },
    assistant: { title: 'Assistant', meta: '// llama-3.3-70b · grounded' },
    profile:   { title: 'Profile',   meta: '// long-term plan' },
    settings:  { title: 'Settings',  meta: '// preferences' },
  }[route] || { title: 'Portfolius' };

  const ScreenMap = {
    dashboard: DashboardScreen,
    holdings:  HoldingsScreen,
    assistant: AssistantScreen,
    profile:   ProfileScreen,
    settings:  ProfileScreen,
  };
  const Screen = ScreenMap[route];

  const palette = PALETTE_DEFS[t.accent] || PALETTE_DEFS.brass;
  const accentStyle = paletteToStyle(palette);

  return (
    <div className={`shell ${mode === 'terminal' ? 'terminal' : ''}`} style={accentStyle}>
      <Sidebar active={route} onNav={setRoute} />
      <Header title={headerFor.title} meta={headerFor.meta} mode={mode} onModeChange={setMode} />
      <main className="main">
        <Screen />
      </main>

      <TweaksPanel>
        <TweakSection label="Accent palette" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {Object.entries(PALETTE_DEFS).map(([key, p]) => {
            const active = t.accent === key;
            return (
              <button key={key}
                onClick={() => setTweak('accent', key)}
                style={{
                  appearance: 'none', border: active ? '1.5px solid #29261b' : '1px solid rgba(0,0,0,0.12)',
                  background: 'rgba(255,255,255,0.6)', borderRadius: 8,
                  padding: '8px 10px', cursor: 'default',
                  textAlign: 'left', display: 'flex', flexDirection: 'column', gap: 6,
                  font: 'inherit', color: 'inherit',
                }}>
                <div style={{ display: 'flex', gap: 3 }}>
                  <span style={{ width: 18, height: 18, borderRadius: 4, background: p[500] }}></span>
                  <span style={{ width: 10, height: 18, borderRadius: 2, background: p[700] }}></span>
                  <span style={{ width: 10, height: 18, borderRadius: 2, background: p[300] }}></span>
                  <span style={{ width: 10, height: 18, borderRadius: 2, background: p[100] }}></span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontWeight: 600, fontSize: 11.5 }}>{p.label}</span>
                  <span style={{ fontSize: 10, opacity: 0.6 }}>{p.blurb}</span>
                </div>
              </button>
            );
          })}
        </div>
        <TweakSection label="Mode" />
        <TweakRadio label="Surface" value={mode}
                    options={['paper', 'terminal']}
                    onChange={(v) => setMode(v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
