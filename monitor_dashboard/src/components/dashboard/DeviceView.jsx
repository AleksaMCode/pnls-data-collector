import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';

import { useLiveCount } from './LiveCountProvider';
import {
  Chip,
  FormControl,
  Grid,
  InputAdornment,
  OutlinedInput,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { Navigate, useParams } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { subscribeToDeviceLiveData } from '../../firebase/firebase';
import { fetchDeviceDataSeries } from '../../statsApi/StatsApi';
import { FilterAlt } from '@mui/icons-material';
import StatCard from './StatCard';
import { useTranslation } from 'react-i18next';

const DEFAULT_FILTERS = ['CERN', 'CERN-Visitors', '*'];
const dataTotalTemplate = [
  {
    id: 'probeRequestCount',
    titleKey: 'common.probeRequests',
    value: 0,
    intervalKey: 'mainGrid.total',
    trend: 'up',
    data: [],
  },
  {
    id: 'ssidCount',
    titleKey: 'common.ssids',
    value: 0,
    intervalKey: 'mainGrid.total',
    trend: 'up',
    data: [],
  },
  {
    id: 'macCount',
    titleKey: 'common.macAddresses',
    value: 0,
    intervalKey: 'mainGrid.total',
    trend: 'up',
    data: [],
  },
];

export default function DeviceView() {
  const { t } = useTranslation();
  const { deviceId } = useParams();
  const [rows, setRows] = useState([]);
  const [filterInput, setFilterInput] = useState('');
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const filtersRef = useRef(filters);
  const bottomRef = useRef(null);
  const { enabled } = useLiveCount();

  const [dataTotal, setDataTotal] = useState(dataTotalTemplate);
  const [totalDataSeriesDates, setTotalDataSeriesDates] = useState(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);

  const ALLOWED_DEVICES = ['RPI-1', 'RPI-2', 'RPI-3'];

  if (!ALLOWED_DEVICES.includes(deviceId)) {
    return <Navigate to="/home" replace />;
  }

  useEffect(() => {
    async function fetchData() {
      try {
        const dataSeriesTotal = await fetchDeviceDataSeries(deviceId);
        setTotalDataSeriesDates(dataSeriesTotal.dayCounts);
        // Update the data array
        setDataTotal((prev) =>
          prev.map((card) => ({
            ...card,
            value:
              dataSeriesTotal[card.id].reduce((sum, value) => sum + value, 0) ??
              0,
            data: dataSeriesTotal[card.id] ?? [],
          })),
        );
        setIsLoadingStats(false);
      } catch (err) {
        console.error('Failed to fetch data for all days:', err);
      }
    }

    setIsLoadingStats(true);
    fetchData();
  }, []);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    if (!deviceId || !enabled) return;

    setRows([]);

    const unsubscribe = subscribeToDeviceLiveData(deviceId, (row) => {
      if (filtersRef.current.includes(row.ssid)) {
        return;
      }
      setRows((prev) => [...prev, row]);
    });

    return () => unsubscribe();
  }, [deviceId, enabled]);
  const handleFilterKeyDown = (e) => {
    if (e.key === 'Enter' && filterInput.trim()) {
      const value = filterInput.trim();

      if (!filters.includes(value)) {
        setFilters((prev) => [...prev, value]);
      }

      setFilterInput('');
      e.preventDefault();
    }
  };

  const filteredRows = rows.filter((row) => !filters.includes(row.ssid));

  useEffect(() => {
    if (filteredRows.length > 0 && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [filteredRows.length]);

  const handleClearFilters = () => {
    setFilters([]);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        {t('deviceView.title', { deviceId })}
      </Typography>
      <Grid
        container
        spacing={2}
        columns={1}
        sx={{ mb: (theme) => theme.spacing(2) }}
      >
        {dataTotal.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 12, lg: 12 }}>
            <StatCard
              {...card}
              title={t(card.titleKey)}
              interval={t(card.intervalKey)}
              hideTrendValues={true}
              dayCount={totalDataSeriesDates}
              isLoading={isLoadingStats}
            />
          </Grid>
        ))}

        {/* SSID Filter Section*/}
        <Grid size={{ xs: 12 }}>
          <Stack spacing={1}>
            <FormControl sx={{ width: '100%' }}>
              <Stack spacing={1}>
                <OutlinedInput
                  size="small"
                  placeholder={t('common.filterSsid')}
                  value={filterInput}
                  onChange={(e) => setFilterInput(e.target.value)}
                  onKeyDown={handleFilterKeyDown}
                  startAdornment={
                    <InputAdornment position="start">
                      <FilterAlt fontSize="small" />
                    </InputAdornment>
                  }
                />
              </Stack>
            </FormControl>

            {filters.length > 0 && (
              <>
                <Tooltip title={t('deviceView.clearAllFilters')}>
                  <Chip
                    label={t('common.clearAll')}
                    color="error"
                    variant="outlined"
                    onClick={handleClearFilters}
                    sx={{ width: '100%' }}
                  />
                </Tooltip>
                <Stack
                  direction="row"
                  spacing={0}
                  flexWrap="wrap"
                  sx={{ gap: 0.5 }}
                >
                  {filters.map((filter) => (
                    <Chip
                      key={filter}
                      label={filter}
                      variant="outlined"
                      color="primary"
                      onDelete={() =>
                        setFilters((prev) => prev.filter((f) => f !== filter))
                      }
                    />
                  ))}
                </Stack>
              </>
            )}
          </Stack>
        </Grid>

        {/* Table Section */}
        <Grid size={{ xs: 12 }}>
          <TableContainer
            component={Paper}
            variant="outlined"
            sx={{
              borderColor: 'divider',
              maxHeight: 540,
              overflowY: 'auto',
            }}
          >
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell
                    sx={{
                      width: '55%',
                      backgroundColor: 'background.paper',
                      fontWeight: 600,
                    }}
                  >
                    {t('deviceView.ssid')}
                  </TableCell>
                  <TableCell
                    sx={{
                      width: '45%',
                      backgroundColor: 'background.paper',
                      fontWeight: 600,
                    }}
                  >
                    {t('deviceView.timestamp')}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredRows.map((row, index) => (
                  <TableRow
                    key={`${row.ssid ?? 'ssid'}-${row.timestamp ?? 'timestamp'}-${index}`}
                    hover
                    sx={(theme) => ({
                      backgroundColor:
                        index % 2 === 0
                          ? theme.palette.background.default
                          : theme.palette.action.hover,
                      '& td': {
                        borderBottom: `1px solid ${theme.palette.divider}`,
                      },
                    })}
                  >
                    <TableCell>{row.ssid || '-'}</TableCell>
                    <TableCell>{row.timestamp || '-'}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell colSpan={2} sx={{ borderBottom: 'none', p: 0 }}>
                    <Box ref={bottomRef} />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>
      </Grid>
    </Box>
  );
}
