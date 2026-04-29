"use client";

import type { Asset, Control, Obligation } from "@/lib/api/types";

/**
 * Obligation graph: obligations → controls → assets.
 * Three columns of nodes connected by hairline curves.
 */
export function ObligationGraph({
  obligations,
  controls,
  assets
}: {
  obligations: Obligation[];
  controls: Control[];
  assets: Asset[];
}) {
  const obs = obligations.slice(0, 6);
  const ctrls = controls.slice(0, 5);
  const ass = assets.filter((a) => ["agent", "tool", "ai_system"].includes(a.type)).slice(0, 5);

  const obW = 260, ctrlW = 220, assW = 260;
  const PAD = 16;
  const colX = [
    PAD + obW / 2,
    480,
    980 - PAD - assW / 2
  ];
  const W = 980;
  const rowGap = 96;
  const top = 48;
  const H = top + Math.max(obs.length, ctrls.length, ass.length) * rowGap;

  const obY = (i: number) => top + i * rowGap;
  const cY = (i: number) => top + (i + (obs.length - ctrls.length) / 2) * rowGap;
  const aY = (i: number) => top + (i + (obs.length - ass.length) / 2) * rowGap;

  const obToCtrl: Array<{ from: [number, number]; to: [number, number] }> = [];
  obs.forEach((o, oi) => {
    ctrls.forEach((c, ci) => {
      if (c.obligations_implemented.includes(o.urn)) {
        obToCtrl.push({
          from: [colX[0] + obW / 2, obY(oi) + 28],
          to: [colX[1] - ctrlW / 2, cY(ci) + 28]
        });
      }
    });
  });
  const ctrlToAsset: Array<{ from: [number, number]; to: [number, number] }> = [];
  ctrls.forEach((_, ci) => {
    ass.slice(0, 3).forEach((_, ai) => {
      ctrlToAsset.push({
        from: [colX[1] + ctrlW / 2, cY(ci) + 28],
        to: [colX[2] - assW / 2, aY(ai) + 28]
      });
    });
  });

  return (
    <div className="border border-rule bg-ink-2 p-6 rounded-sm">
      <svg viewBox={`0 0 ${W} ${H + 40}`} className="w-full h-auto" role="img" aria-label="Obligation graph">
        <ColumnHeader x={colX[0]} label="Obligations" />
        <ColumnHeader x={colX[1]} label="Controls" />
        <ColumnHeader x={colX[2]} label="Assets" />

        {obToCtrl.map((e, i) => <Edge key={"oc" + i} {...e} />)}
        {ctrlToAsset.map((e, i) => <Edge key={"ca" + i} {...e} />)}

        {obs.map((o, i) => <ObligationNode key={o.id} obligation={o} x={colX[0]} y={obY(i)} w={obW} />)}
        {ctrls.map((c, i) => <ControlNode key={c.id} control={c} x={colX[1]} y={cY(i)} w={ctrlW} />)}
        {ass.map((a, i) => <AssetNode key={a.id} asset={a} x={colX[2]} y={aY(i)} w={assW} />)}
      </svg>
    </div>
  );
}

function ColumnHeader({ x, label }: { x: number; label: string }) {
  return (
    <text
      x={x}
      y={24}
      fontFamily="General Sans"
      fontSize="11"
      fontWeight={500}
      letterSpacing="1.2"
      fill="var(--paper-fade)"
      textAnchor="middle"
    >
      {label.toUpperCase()}
    </text>
  );
}

function Edge({ from, to }: { from: [number, number]; to: [number, number] }) {
  const [x1, y1] = from;
  const [x2, y2] = to;
  const c1x = (x1 + x2) / 2;
  const path = `M ${x1} ${y1} C ${c1x} ${y1}, ${c1x} ${y2}, ${x2} ${y2}`;
  return <path d={path} stroke="var(--rule-bright)" strokeWidth={0.75} fill="none" />;
}

function ObligationNode({ obligation, x, y, w }: { obligation: Obligation; x: number; y: number; w: number }) {
  const h = 60;
  return (
    <g transform={`translate(${x - w / 2}, ${y})`}>
      <rect x={0} y={0} width={w} height={h} fill="var(--ink)" stroke="var(--rule)" strokeWidth={0.75} rx={2} />
      <text x={12} y={18} fontFamily="JetBrains Mono" fontSize="10" fill="var(--gold-bright)" letterSpacing="1.2">
        {obligation.framework.replace("_", " ").toUpperCase()}
      </text>
      <text x={12} y={36} fontFamily="General Sans" fontSize="13" fontWeight={500} fill="var(--paper)">
        {obligation.citation}
      </text>
      <text x={12} y={51} fontFamily="General Sans" fontSize="11" fill="var(--paper-fade)">
        {truncate(obligation.text, 50)}
      </text>
    </g>
  );
}

function ControlNode({ control, x, y, w }: { control: Control; x: number; y: number; w: number }) {
  const h = 60;
  return (
    <g transform={`translate(${x - w / 2}, ${y})`}>
      <rect x={0} y={0} width={w} height={h} fill="var(--ink)" stroke="var(--gold-dim)" strokeWidth={0.75} rx={2} />
      <text x={12} y={18} fontFamily="General Sans" fontSize="11.5" fontWeight={600} fill="var(--paper)">
        {control.name}
      </text>
      <text x={12} y={36} fontFamily="JetBrains Mono" fontSize="10" fill="var(--paper-fade)">
        {control.package}
      </text>
      <text x={12} y={51} fontFamily="General Sans" fontSize="11" fill="var(--paper-fade)">
        {control.obligations_implemented.length} obligation{control.obligations_implemented.length === 1 ? "" : "s"}
      </text>
    </g>
  );
}

function AssetNode({ asset, x, y, w }: { asset: Asset; x: number; y: number; w: number }) {
  const h = 60;
  return (
    <g transform={`translate(${x - w / 2}, ${y})`}>
      <rect x={0} y={0} width={w} height={h} fill="var(--ink)" stroke="var(--rule)" strokeWidth={0.75} rx={2} />
      <text x={12} y={18} fontFamily="JetBrains Mono" fontSize="10" fill="var(--paper-fade)" letterSpacing="1.2">
        {asset.type.toUpperCase()}
      </text>
      <text x={12} y={36} fontFamily="General Sans" fontSize="13" fontWeight={500} fill="var(--paper)">
        {asset.name}
      </text>
      <text x={12} y={51} fontFamily="JetBrains Mono" fontSize="10" fill="var(--paper-fade)">
        tier {asset.risk_tier} · {asset.lifecycle}
      </text>
    </g>
  );
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
