import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';

import { useLiveCount } from './LiveCountProvider';
import {
  Chip,
  FormControl,
  Grid,
  Grow,
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
import {
  fetchDeviceDataSeries,
  subscribeToDeviceLiveData,
} from '../../firebase/firebase';
import { FilterAlt, HighlightOff } from '@mui/icons-material';
import StatCard from './StatCard';

const DEFAULT_FILTERS = ['CERN', 'CERN-Visitors', '*'];
const dataTotalTemplate = [
  {
    id: 'probeRequestCount',
    title: 'Probe Requests',
    value: 0,
    interval: 'Total',
    trend: 'up',
    data: [],
  },
  {
    id: 'ssidCount',
    title: 'SSIDs',
    value: 0,
    interval: 'Total',
    trend: 'up',
    data: [],
  },
  {
    id: 'macCount',
    title: 'MAC addresses',
    value: 0,
    interval: 'Total',
    trend: 'up',
    data: [],
  },
];

export default function DeviceView() {
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

  useEffect(() => {
    if (rows.length > 0 && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [rows]);

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

  const handleClearFilters = () => {
    setFilters([]);
  };

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Device: {deviceId}
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
                  placeholder="Filter SSID…"
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
                <Tooltip title="Clear all filters">
                  <Chip
                    label="Clear all"
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
          <TableContainer component={Paper} sx={{ width: '100%' }}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: 'primary.main' }}>
                  <TableCell sx={{ width: '50%' }}>SSID</TableCell>
                  <TableCell sx={{ width: '50%' }}>Timestamp</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row, idx) => (
                  <Grow in timeout={300} key={idx}>
                    <TableRow
                      key={idx}
                      sx={{
                        backgroundColor:
                          idx % 2 === 0 ? 'background.paper' : 'action.hover',
                      }}
                    >
                      <TableCell sx={{ width: '50%' }}>{row.ssid}</TableCell>
                      <TableCell sx={{ width: '50%' }}>
                        {row.timestamp}
                      </TableCell>
                    </TableRow>
                  </Grow>
                ))}
                <TableRow ref={bottomRef} />
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>
      </Grid>
    </Box>
  );
}
