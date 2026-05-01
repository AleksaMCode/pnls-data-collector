import { DataGrid } from '@mui/x-data-grid';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  ComposableMap,
  Geographies,
  Geography,
} from '@vnedyalk0v/react19-simple-maps';
import { useEffect, useMemo, useState } from 'react';

// Data from https://raw.githubusercontent.com/subyfly/topojson/refs/heads/master/world-countries.json'
const WORLD_TOPOLOGY_URL = '/world-countries.json';

const columns = [
  {
    field: 'company',
    headerName: 'Company',
    flex: 1.5,
    minWidth: 240,
  },
  {
    field: 'country',
    headerName: 'Country (alpha3)',
    flex: 1,
    minWidth: 150,
    renderCell: (params) => params.row.country || '-',
  },
  {
    field: 'count',
    headerName: 'Count',
    type: 'number',
    flex: 0.8,
    minWidth: 120,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => Number(params.row.count ?? 0).toLocaleString(),
  },
  {
    field: 'percentage',
    headerName: 'Percentage',
    type: 'number',
    flex: 0.8,
    minWidth: 130,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => `${Number(params.row.percentage ?? 0).toFixed(4)}%`,
  },
];

export default function ManufacturerDataGrid({ manufacturers = [] }) {
  const [worldGeography, setWorldGeography] = useState(null);
  const [isMapExpanded, setIsMapExpanded] = useState(false);
  const [showExpandTooltip, setShowExpandTooltip] = useState(false);

  const rows = manufacturers.map((manufacturer, index) => ({
    id: `${manufacturer.company}-${manufacturer.country ?? 'NA'}-${index}`,
    company: manufacturer.company ?? '-',
    country: manufacturer.country ?? null,
    count: Number(manufacturer.count ?? 0),
    percentage: Number(manufacturer.percentage ?? 0),
  }));

  const countryCounts = useMemo(() => {
    const acc = {};

    for (const row of rows) {
      const code = row.country?.toUpperCase().trim();
      if (!code) continue;

      acc[code] = (acc[code] ?? 0) + Number(row.count ?? 0);
    }

    return acc;
  }, [rows]);

  useEffect(() => {
    let isMounted = true;

    const loadWorldGeography = async () => {
      try {
        const response = await fetch(WORLD_TOPOLOGY_URL);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        if (isMounted) {
          setWorldGeography(data);
        }
      } catch (err) {
        console.error('Failed to load geography data:', err);
      }
    };

    loadWorldGeography();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <Box>
      <DataGrid
        rows={rows}
        columns={columns}
        disableRowSelectionOnClick
        initialState={{
          pagination: { paginationModel: { pageSize: 5 } },
        }}
        pageSizeOptions={[5, 10, 20]}
        getRowClassName={(params) =>
          params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
        }
        sx={{
          '& .MuiDataGrid-row': {
            backgroundColor: 'common.white',
          },
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'primary.50',
          },
        }}
      />

      <Accordion
        sx={{ mt: 2 }}
        expanded={isMapExpanded}
        onChange={(_, expanded) => {
          setIsMapExpanded(expanded);
          setShowExpandTooltip(false);
        }}
      >
        <Tooltip
          title="Click to expand and see the map"
          arrow
          open={!isMapExpanded && showExpandTooltip}
          onOpen={() => setShowExpandTooltip(true)}
          onClose={() => setShowExpandTooltip(false)}
          disableHoverListener={isMapExpanded}
          disableFocusListener
          disableTouchListener
          disableInteractive
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">
              Manufacturer data by country (world map)
            </Typography>
          </AccordionSummary>
        </Tooltip>
        <AccordionDetails>
          <Paper sx={{ p: 2 }}>
            {worldGeography ? (
              <ComposableMap
                projection="geoMercator"
                projectionConfig={{
                  scale: 130,
                  center: [0, 20],
                }}
                style={{ width: '100%', height: 'auto' }}
              >
                <Geographies geography={worldGeography}>
                  {({ geographies }) =>
                    geographies.map((geo, index) => {
                      const alpha3 =
                        geo.properties?.ISO_A3 ??
                        geo.properties?.iso_a3 ??
                        geo.properties?.ADM0_A3 ??
                        geo.id;
                      const normalizedAlpha3 = String(alpha3 ?? '')
                        .toUpperCase()
                        .trim();
                      const count = countryCounts[normalizedAlpha3] ?? 0;
                      const hasData = count > 0;
                      return (
                        <Geography
                          key={`${geo.rsmKey ?? 'rsm'}-${geo.id ?? 'noid'}-${normalizedAlpha3 || 'geo'}-${index}`}
                          geography={geo}
                          fill={hasData ? '#0b57adff' : '#F5F5F5'}
                          stroke="#90CAF9"
                          strokeWidth={0.4}
                          style={{
                            default: { outline: 'none' },
                            hover: {
                              fill: '#1E88E5',
                              outline: 'none',
                              cursor: 'pointer',
                            },
                          }}
                        >
                          <title>
                            {`${geo.properties?.name ?? geo.properties?.NAME ?? geo.properties?.ADMIN ?? 'Unknown'}: ${count.toLocaleString()}`}
                          </title>
                        </Geography>
                      );
                    })
                  }
                </Geographies>
              </ComposableMap>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Failed to load geography data
              </Typography>
            )}
          </Paper>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
