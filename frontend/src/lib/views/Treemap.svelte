<script>
  // Treemap view. Tile area = current value (base currency); colour = day or total % change.
  // Rendered as absolutely-positioned divs (cheaper text layout than SVG, CSS transitions for free).
  import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy';
  import { makeColorScale, textOn } from '../themes.js';
  import { groupKey } from '../portfolio.js';
  import { money, pct, price as fmtPrice, MASK } from '../format.js';

  let { rows, settings, theme } = $props();

  let w = $state(0);
  let h = $state(0);
  let hover = $state(null);
  let mx = $state(0);
  let my = $state(0);

  const base = $derived(settings.baseCurrency);
  const hideAmounts = $derived(settings.privacy || !settings.showTileValues);
  const colorBy = $derived(settings.colorMetric);
  const scale = $derived(
    makeColorScale(theme, colorBy === 'day' ? Number(settings.dayFullScale) || 3 : Number(settings.totalFullScale) || 50)
  );

  const layout = $derived.by(() => {
    const items = rows.filter((r) => r.value > 0);
    if (!w || !h || !items.length) return { leaves: [], groups: [] };
    const grouped = settings.groupBy !== 'none';
    let data;
    if (grouped) {
      const m = new Map();
      for (const r of items) {
        const k = groupKey(r, settings.groupBy);
        if (!m.has(k)) m.set(k, []);
        m.get(k).push(r);
      }
      data = { name: 'root', children: [...m].map(([name, children]) => ({ name, children, isGroup: true })) };
    } else {
      data = { name: 'root', children: items };
    }
    const root = hierarchy(data, (d) => d.children)
      .sum((d) => (d.children ? 0 : d.value))
      .sort((a, b) => b.value - a.value);
    treemap()
      .tile(treemapSquarify.ratio(1.3))
      .size([w, h])
      .paddingInner(grouped ? 3 : 1)
      .paddingTop((n) => (n.depth === 1 ? 18 : 0))
      .round(true)(root);

    const leaves = root.leaves().map((n) => tile(n));
    const groups = grouped
      ? (root.children || []).map((g) => ({
          name: g.data.name,
          x: g.x0, y: g.y0, w: g.x1 - g.x0, h: g.y1 - g.y0,
          value: g.value,
          share: (g.value / root.value) * 100,
          dayPct: weightedPct(g.leaves().map((l) => l.data), 'day'),
        }))
      : [];
    return { leaves, groups };
  });

  function weightedPct(rs, kind) {
    if (kind === 'day') {
      const chg = rs.reduce((a, r) => a + r.dayChange, 0);
      const prev = rs.reduce((a, r) => a + r.value, 0) - chg;
      return prev > 0 ? (chg / prev) * 100 : null;
    }
    const inv = rs.reduce((a, r) => a + r.invested, 0);
    const val = rs.reduce((a, r) => a + r.value, 0);
    return inv > 0 ? (val / inv - 1) * 100 : null;
  }

  function tile(n) {
    const r = n.data;
    const tw = n.x1 - n.x0;
    const th = n.y1 - n.y0;
    const primary = colorBy === 'day' ? r.dayPct : r.totalPct;
    const secondary = colorBy === 'day' ? r.totalPct : r.dayPct;
    const bg = scale(primary);
    const label = displaySymbol(r);
    const fs = Math.max(8, Math.min(44, (tw / Math.max(4, label.length)) * 1.45, th / 3.4));
    return {
      r, x: n.x0, y: n.y0, w: tw, h: th, bg, fg: textOn(bg), fs, label,
      primary, secondary,
      showLabel: tw > 22 && th > 12,
      showPct: th > fs * 2.3 && tw > 34,
      showSecondary: settings.labelMetric === 'both' && th > fs * 3.3 && tw > 60,
      showValue: !hideAmounts && th > fs * 4.2 && tw > 50,
    };
  }

  function displaySymbol(r) {
    if (r.type === 'MF') return shortFundName(r.name) || r.symbol;
    return r.symbol || r.name;
  }

  function shortFundName(name) {
    return (name || '')
      .replace(/\s*-\s*(Direct|Regular).*$/i, '')
      .replace(/\b(Fund|Plan|Growth|Option)\b/gi, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function move(e) {
    mx = e.clientX;
    my = e.clientY;
  }

  const tipStyle = $derived.by(() => {
    const x = mx + 260 > window.innerWidth ? mx - 260 - 12 : mx + 14;
    const y = my + 220 > window.innerHeight ? Math.max(8, my - 220) : my + 14;
    return `left:${x}px;top:${y}px`;
  });
  const otherLabel = $derived(colorBy === 'day' ? 'Total' : 'Day');
</script>

<div
  class="treemap"
  bind:clientWidth={w}
  bind:clientHeight={h}
  onmousemove={move}
  onmouseleave={() => (hover = null)}
  role="img"
  aria-label="Portfolio treemap"
>
  {#each layout.groups as g (g.name)}
    <div class="group" style="left:{g.x}px;top:{g.y}px;width:{g.w}px;height:{g.h}px">
      <div class="glabel">
        <span>{g.name}</span>
        <span class="gmeta">{g.share.toFixed(1)}%{#if g.dayPct != null}&nbsp;·&nbsp;{pct(g.dayPct)}{/if}</span>
      </div>
    </div>
  {/each}

  {#each layout.leaves as t (t.r.id)}
    <div
      class="tile"
      style="left:{t.x}px;top:{t.y}px;width:{t.w}px;height:{t.h}px;background:{t.bg};color:{t.fg};font-size:{t.fs}px"
      onmouseenter={() => (hover = t.r)}
      role="presentation"
    >
      {#if t.showLabel}
        <div class="sym">{t.label}</div>
        {#if t.showPct}<div class="pct">{pct(t.primary)}</div>{/if}
        {#if t.showSecondary}<div class="sec">{otherLabel} {pct(t.secondary)}</div>{/if}
        {#if t.showValue}
          <div class="val">
            {#if (settings.tileAmountMode || 'value') !== 'invested'}
              <div>Value {money(t.r.value, base)}{#if settings.showTilePrice && t.r.price != null}&nbsp;·&nbsp;{fmtPrice(t.r.price, t.r.currency)}{/if}</div>
            {/if}
            {#if (settings.tileAmountMode || 'value') !== 'value'}
              <div>Invested {t.r.costKnown ? money(t.r.invested, base) : '—'}</div>
            {/if}
          </div>
        {/if}
      {/if}
      {#if !t.r.live && t.r.type !== 'OTHER' && t.r.priceOverride == null && t.w > 30}
        <span class="stale" title="No live quote yet">•</span>
      {/if}
    </div>
  {/each}

  {#if hover}
    <div class="tip" style={tipStyle}>
      <div class="tname">{hover.name || hover.symbol}</div>
      <div class="muted small">{hover.symbol}{hover.exchange ? ` · ${hover.exchange}` : ''} · {hover.assetClass}{hover.broker ? ` · ${hover.broker}` : ''}</div>
      <table>
        <tbody>
          <tr><td>Price</td><td>{fmtPrice(hover.price, hover.currency)} <span class="muted small">{hover.quoteSource}</span></td></tr>
          <tr><td>Day</td><td class={hover.dayPct > 0 ? 'pos' : hover.dayPct < 0 ? 'neg' : ''}>{pct(hover.dayPct)}{#if !settings.privacy}&nbsp;({money(hover.dayChange, base, { sign: true })}){/if}</td></tr>
          <tr><td>Total</td><td class={hover.totalPct > 0 ? 'pos' : hover.totalPct < 0 ? 'neg' : ''}>{pct(hover.totalPct)}{#if !settings.privacy}&nbsp;({money(hover.totalChange, base, { sign: true })}){/if}</td></tr>
          <tr><td>Value</td><td>{settings.privacy ? MASK : money(hover.value, base, { compact: false })}</td></tr>
          <tr><td>Invested</td><td>{settings.privacy ? MASK : hover.costKnown ? money(hover.invested, base, { compact: false }) : 'cost unknown'}</td></tr>
          <tr><td>Qty · Avg</td><td>{settings.privacy ? MASK : `${+hover.qty.toFixed(4)} · ${hover.costKnown ? fmtPrice(hover.avgPrice, hover.currency) : 'cost unknown'}`}</td></tr>
          {#if hover.parts?.length > 1}
            <tr><td>Accounts</td><td>{#each hover.parts as p}<div>{p.broker || 'Unassigned'}{settings.privacy ? '' : ` · ${+p.qty.toFixed(4)}`}</div>{/each}</td></tr>
          {/if}
          {#if hover.sector}<tr><td>Sector</td><td>{hover.sector}</td></tr>{/if}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .treemap { position: absolute; inset: 0; overflow: hidden; background: var(--gap); }
  .group { position: absolute; pointer-events: none; transition: all .4s ease; }
  .glabel {
    display: flex; justify-content: space-between; gap: 8px; height: 18px; line-height: 18px;
    padding: 0 4px; font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: .04em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .gmeta { opacity: .8; }
  .tile {
    position: absolute; overflow: hidden; display: flex; flex-direction: column;
    align-items: center; justify-content: center; text-align: center; line-height: 1.15;
    border-radius: var(--radius); padding: 2px;
    transition: left .4s ease, top .4s ease, width .4s ease, height .4s ease, background-color .8s ease;
  }
  .tile:hover { outline: 2px solid color-mix(in srgb, currentColor 60%, transparent); outline-offset: -2px; z-index: 1; }
  .sym { font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pct { font-size: .78em; opacity: .95; font-variant-numeric: tabular-nums; }
  .sec { font-size: .55em; opacity: .8; font-variant-numeric: tabular-nums; }
  .val { font-size: .55em; opacity: .8; margin-top: .15em; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .stale { position: absolute; top: 2px; right: 5px; font-size: 12px; opacity: .6; }
  .tip {
    position: fixed; z-index: 20; width: 260px; pointer-events: none; padding: 10px 12px;
    background: var(--surface); color: var(--text); border-radius: var(--radius);
    border: 1px solid color-mix(in srgb, var(--muted) 35%, transparent);
    box-shadow: 0 8px 30px rgba(0, 0, 0, .35); font-size: 12px;
  }
  .tname { font-weight: 700; font-size: 13px; margin-bottom: 2px; }
  .tip table { width: 100%; margin-top: 6px; border-collapse: collapse; }
  .tip td { padding: 2px 0; font-variant-numeric: tabular-nums; }
  .tip td:first-child { color: var(--muted); width: 72px; }
</style>
