import { DataGrid } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';
import {
  ComposableMap,
  Geographies,
  Geography,
} from '@vnedyalk0v/react19-simple-maps';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

// Data from https://raw.githubusercontent.com/subyfly/topojson/refs/heads/master/world-countries.json'
const WORLD_TOPOLOGY_URL = '/world-countries.json';

// Memoized so the (expensive) SVG world map only re-renders when the geography
// or the aggregated country counts actually change by reference.
const WorldMap = memo(function WorldMap({ worldGeography, countryCounts }) {
  const theme = useTheme();

  const mapColors = {
    withData:
      theme.palette.mode === 'dark'
        ? theme.palette.primary.light
        : theme.palette.primary.main,
    withoutData:
      theme.palette.mode === 'dark'
        ? alpha(theme.palette.common.white, 0.12)
        : theme.palette.grey[100],
    stroke:
      theme.palette.mode === 'dark'
        ? alpha(theme.palette.common.white, 0.28)
        : theme.palette.divider,
    hover:
      theme.palette.mode === 'dark'
        ? theme.palette.primary.main
        : theme.palette.primary.dark,
  };

  return (
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
                fill={hasData ? mapColors.withData : mapColors.withoutData}
                stroke={mapColors.stroke}
                strokeWidth={0.4}
                style={{
                  default: { outline: 'none' },
                  hover: {
                    fill: mapColors.hover,
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
  );
});

export default function ManufacturerDataGrid({
  manufacturers = [],
  loading = false,
  mapReady = true,
}) {
  const { t } = useTranslation();
  const [worldGeography, setWorldGeography] = useState(null);
  const columns = useMemo(
    () => [
      {
        field: 'company',
        headerName: t('manufacturer.company'),
        flex: 1.5,
        minWidth: 240,
      },
      {
        field: 'country',
        headerName: t('manufacturer.country'),
        flex: 1,
        minWidth: 150,
        renderCell: (params) => params.row.country || '-',
      },
      {
        field: 'count',
        headerName: t('manufacturer.count'),
        type: 'number',
        flex: 0.8,
        minWidth: 120,
        align: 'right',
        headerAlign: 'right',
        renderHeader: () => (
          <Tooltip title={t('manufacturer.countTooltip')}>
            <span>{t('manufacturer.count')}</span>
          </Tooltip>
        ),
        renderCell: (params) => Number(params.row.count ?? 0).toLocaleString(),
      },
      {
        field: 'percentage',
        headerName: t('manufacturer.percentage'),
        type: 'number',
        flex: 0.8,
        minWidth: 130,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) =>
          `${Number(params.row.percentage ?? 0).toFixed(4)}%`,
      },
    ],
    [t],
  );

  const rows = useMemo(
    () =>
      manufacturers.map((manufacturer, index) => ({
        id: `${manufacturer.company}-${manufacturer.country ?? 'NA'}-${index}`,
        company: manufacturer.company ?? '-',
        country: manufacturer.country ?? null,
        count: Number(manufacturer.count ?? 0),
        percentage: Number(manufacturer.percentage ?? 0),
      })),
    [manufacturers],
  );

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
        checkboxSelection={false}
        rows={rows}
        columns={columns}
        loading={loading}
        disableRowSelectionOnClick
        disableColumnResize
        // density="compact"
        initialState={{
          pagination: { paginationModel: { pageSize: 5 } },
        }}
        pageSizeOptions={[5, 10, 20]}
        getRowClassName={(params) =>
          params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
        }
        slotProps={{
          loadingOverlay: {
            variant: 'skeleton',
            noRowsVariant: 'skeleton',
          },
          filterPanel: {
            filterFormProps: {
              logicOperatorInputProps: {
                variant: 'outlined',
                size: 'small',
              },
              columnInputProps: {
                variant: 'outlined',
                size: 'small',
                sx: { mt: 'auto' },
              },
              operatorInputProps: {
                variant: 'outlined',
                size: 'small',
                sx: { mt: 'auto' },
              },
              valueInputProps: {
                InputComponentProps: {
                  variant: 'outlined',
                  size: 'small',
                },
              },
            },
          },
        }}
      />

      <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
        {t('manufacturer.mapTitle')}
      </Typography>
      <Paper sx={{ p: 2 }}>
        {mapReady && worldGeography && manufacturers.length > 0 ? (
          <WorldMap
            worldGeography={worldGeography}
            countryCounts={countryCounts}
          />
        ) : (
          <Typography variant="body2" color="text.secondary">
            {t('common.loadingMap')}
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
