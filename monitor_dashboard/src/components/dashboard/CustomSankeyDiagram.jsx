import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useMemo } from 'react';

function buildSankeyGraph(data) {
  const deviceNodes = [];
  const companyNodesMap = new Map();
  const countryNodesMap = new Map();
  const links = [];

  const companyCountryCounts = new Map();

  for (const [deviceName, manufacturers] of Object.entries(data ?? {})) {
    const deviceLabel = String(deviceName).toUpperCase();
    const deviceId = `device:${deviceLabel}`;
    deviceNodes.push({ id: deviceId, label: deviceLabel, value: 0, layer: 0 });

    for (const [companyName, info] of Object.entries(manufacturers ?? {})) {
      if (!companyName) continue;

      const country = info?.country
        ? String(info.country).toUpperCase()
        : 'UNK';
      const companyId = `company:${companyName}`;
      const countryId = `country:${country}`;

      if (!companyNodesMap.has(companyId)) {
        companyNodesMap.set(companyId, {
          id: companyId,
          label: companyName,
          value: 0,
          layer: 1,
        });
      }
      if (!countryNodesMap.has(countryId)) {
        countryNodesMap.set(countryId, {
          id: countryId,
          label: country,
          value: 0,
          layer: 2,
        });
      }

      links.push({ source: deviceId, target: companyId, value: 1 });
      deviceNodes[deviceNodes.length - 1].value += 1;
      companyNodesMap.get(companyId).value += 1;

      const c2countryKey = `${companyId}->${countryId}`;
      companyCountryCounts.set(
        c2countryKey,
        (companyCountryCounts.get(c2countryKey) ?? 0) + 1,
      );
    }
  }

  for (const [key, value] of companyCountryCounts.entries()) {
    const [source, target] = key.split('->');
    links.push({ source, target, value });
    countryNodesMap.get(target).value += value;
  }

  const companyNodes = Array.from(companyNodesMap.values()).sort(
    (a, b) => b.value - a.value,
  );
  const countryNodes = Array.from(countryNodesMap.values()).sort(
    (a, b) => b.value - a.value,
  );

  return {
    nodes: [...deviceNodes, ...companyNodes, ...countryNodes],
    links,
  };
}

function layoutSankey(graph) {
  const chartWidth = 1400;
  const topPadding = 12;
  const bottomPadding = 12;
  const gap = 8;
  const nodeWidth = 14;
  const layerX = [80, 620, 1160];

  const layers = [0, 1, 2].map((layer) =>
    graph.nodes
      .filter((n) => n.layer === layer)
      .sort((a, b) => b.value - a.value),
  );

  const maxLayerSize = Math.max(...layers.map((l) => l.length), 1);
  const chartHeight = Math.max(760, maxLayerSize * 34);
  const drawableHeight = chartHeight - topPadding - bottomPadding;

  const layerScales = layers.map((layerNodes) => {
    if (layerNodes.length === 0) return 1;
    const totalValue = layerNodes.reduce((sum, n) => sum + n.value, 0);
    const gapSpace = gap * (layerNodes.length - 1);
    return totalValue > 0 ? (drawableHeight - gapSpace) / totalValue : 1;
  });

  const linkScale = Math.max(
    1,
    Math.min(...layerScales.filter((v) => Number.isFinite(v))),
  );

  const positionedNodes = new Map();
  layers.forEach((layerNodes, layerIdx) => {
    let yCursor = topPadding;
    for (const node of layerNodes) {
      const height = Math.max(10, node.value * layerScales[layerIdx]);
      positionedNodes.set(node.id, {
        ...node,
        x: layerX[layerIdx],
        y: yCursor,
        height,
        outgoingCursor: yCursor,
        incomingCursor: yCursor,
      });
      yCursor += height + gap;
    }
  });

  const coloredLinks = graph.links.map((link) => ({
    ...link,
    width: Math.max(1, link.value * linkScale),
  }));
  coloredLinks.sort((a, b) => b.width - a.width);

  const linkPaths = [];
  for (const link of coloredLinks) {
    const sourceNode = positionedNodes.get(link.source);
    const targetNode = positionedNodes.get(link.target);
    if (!sourceNode || !targetNode) continue;

    const startY = sourceNode.outgoingCursor + link.width / 2;
    const endY = targetNode.incomingCursor + link.width / 2;
    sourceNode.outgoingCursor += link.width + 1;
    targetNode.incomingCursor += link.width + 1;

    const startX = sourceNode.x + nodeWidth;
    const endX = targetNode.x;
    const curve = (endX - startX) * 0.5;
    const path = `M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}`;

    linkPaths.push({
      path,
      width: link.width,
      sourceLayer: sourceNode.layer,
      value: link.value,
      sourceLabel: sourceNode.label,
      targetLabel: targetNode.label,
    });
  }

  return {
    chartWidth,
    chartHeight,
    nodeWidth,
    nodes: Array.from(positionedNodes.values()),
    links: linkPaths,
  };
}

export default function CustomSankeyDiagram({ sankeyData }) {
  const sankeyGraph = useMemo(() => {
    if (!sankeyData || Object.keys(sankeyData).length === 0) {
      return { nodes: [], links: [] };
    }
    return buildSankeyGraph(sankeyData);
  }, [sankeyData]);

  const sankeyLayout = useMemo(() => layoutSankey(sankeyGraph), [sankeyGraph]);
  const hasSankeyData = sankeyGraph.links.length > 0;

  if (!hasSankeyData) {
    return (
      <Typography variant="body2" color="text.secondary">
        No Sankey data available.
      </Typography>
    );
  }

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <svg
        width={sankeyLayout.chartWidth}
        height={sankeyLayout.chartHeight}
        role="img"
        aria-label="Sankey diagram of device, company, and country"
      >
        {sankeyLayout.links.map((link, index) => (
          <path
            key={`link-${index}`}
            d={link.path}
            fill="none"
            stroke={link.sourceLayer === 0 ? '#64b5f6' : '#81c784'}
            strokeOpacity={0.45}
            strokeWidth={link.width}
          >
            <title>{`${link.sourceLabel} -> ${link.targetLabel}: ${link.value}`}</title>
          </path>
        ))}

        {sankeyLayout.nodes.map((node) => (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y}
              width={sankeyLayout.nodeWidth}
              height={node.height}
              rx={2}
              fill={
                node.layer === 0
                  ? '#1976d2'
                  : node.layer === 1
                    ? '#2e7d32'
                    : '#ed6c02'
              }
            >
              <title>{`${node.label} (${node.value})`}</title>
            </rect>
            <text
              x={
                node.layer === 2
                  ? node.x - 8
                  : node.x + sankeyLayout.nodeWidth + 8
              }
              y={node.y + node.height / 2}
              dominantBaseline="middle"
              textAnchor={node.layer === 2 ? 'end' : 'start'}
              fontSize="11"
              fill="#424242"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </Box>
  );
}
