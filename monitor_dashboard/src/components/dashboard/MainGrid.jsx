import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CustomizedDataGrid from './CustomizedDataGrid';
import ManufacturerDataGrid from './ManufacturerDataGrid';
import HighlightedCard from './HighlightedCard';
import CapturedDataBarChart from './CapturedDataBarChart';
import SessionsChart from './SessionsChart';
import StatCard from './StatCard';
import { useEffect, useRef, useState } from 'react';
import { subscribeToLiveProbeRequestCount } from '../../firebase/firebase';
import {
  fetchAllDataSeries,
  fetchManufacturersData,
  fetchLast30DaysTotalsWithSeries,
  fetchPrevious30DaysTotals,
  fetchSankeyData,
  fetchTotalPerDeviceStats,
  fetchTotalStats,
  fetchProbeRequestsPerDeviceLastNDays,
} from '../../statsApi/StatsApi';
import { useLiveCount } from './LiveCountProvider';
import MultiSeriesRadarChart from './MultiSeriesRadarChart';

const data = [
  {
    id: 'probeRequestCount',
    title: 'Probe Requests',
    value: 0,
    prevValue: 0,
    interval: 'Last 30 days',
    data: [
      200, 24, 220, 260, 240, 380, 100, 240, 280, 240, 300, 340, 320, 360, 340,
      380, 360, 400, 380, 420, 400, 640, 340, 460, 440, 480, 460, 600, 880, 920,
    ],
  },
  {
    id: 'ssidCount',
    title: 'SSIDs',
    value: 0,
    prevValue: 0,
    interval: 'Last 30 days',
    data: [
      1640, 1250, 970, 1130, 1050, 900, 720, 1080, 900, 450, 920, 820, 840, 600,
      820, 780, 800, 760, 380, 740, 660, 620, 840, 500, 520, 480, 400, 360, 300,
      220,
    ],
  },
  {
    id: 'macCount',
    title: 'MAC addresses',
    value: 0,
    prevValue: 0,
    interval: 'Last 30 days',
    data: [
      500, 400, 510, 530, 520, 600, 530, 520, 510, 730, 520, 510, 530, 620, 510,
      530, 520, 410, 530, 520, 610, 530, 520, 610, 530, 420, 510, 430, 520, 510,
    ],
  },
];

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
    interval: 'Total (unique)',
    trend: 'up',
    data: [],
  },
  {
    id: 'macCount',
    title: 'MAC addresses',
    value: 0,
    interval: 'Total (unique)',
    trend: 'up',
    data: [],
  },
];

export default function MainGrid() {
  // Total amount of captured data
  const [dataTotal, setDataTotal] = useState(dataTotalTemplate);
  // Initial count for Probe Requsts
  const [initialCount, setInitialCount] = useState(0);
  // Live count of Probe Requests
  const [liveCount, setLiveCount] = useState(0);
  const [isLoadingLiveCount, setIsLoadingLiveCount] = useState(false);
  // TODO Store devices somewhere else or better yet fetch from Firebase device names
  const devices = ['RPI-1', 'RPI-2', 'RPI-3'];
  const { enabled } = useLiveCount();
  // Last 30 days data
  const [dataLast30Days, setDataLast30Days] = useState(data);
  const [totalDataSeriesDates, setTotalDataSeriesDates] = useState(null);
  const [perDeviceTotalData, setPerDeviceTotalData] = useState(null);
  const [probeSeriesPerDevice, setProbeSeriesPerDevice] = useState(null);
  const [sankeyData, setSankeyData] = useState({});
  const [isLoadingTotalStats, setIsLoadingTotalStats] = useState(true);
  const [manufacturers, setManufacturers] = useState([]);
  const [isLoadingManufacturers, setIsLoadingManufacturers] = useState(false);
  const [isManufacturerExpanded, setIsManufacturerExpanded] = useState(false);
  // Only render the heavy world map once the accordion has finished expanding,
  // so the open/close animation stays smooth.
  const [isManufacturerEntered, setIsManufacturerEntered] = useState(false);
  // Guards so the lazy-loaded sections only fire their API call once, on first expand.
  const hasFetchedManufacturers = useRef(false);
  const hasFetchedSankey = useRef(false);

  useEffect(() => {
    fetchProbeRequestsPerDeviceLastNDays(30)
      .then((data) => {
        setProbeSeriesPerDevice(data);
      })
      .catch((err) => {
        console.error('Failed to fetch probe series:', err);
      });
  }, []);
  useEffect(() => {
    fetchTotalPerDeviceStats()
      .then((data) => {
        setPerDeviceTotalData(data);
      })
      .catch((err) => {
        console.error('Failed to fetch all series:', err);
      });
  }, []);

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch both periods in parallel to avoid a request waterfall.
        const [last30, prev30] = await Promise.all([
          // Fetch last 30 days totals & series
          fetchLast30DaysTotalsWithSeries(),
          // Fetch previous 30 days totals & series
          fetchPrevious30DaysTotals(),
        ]);

        // Update the data array
        setDataLast30Days((prev) =>
          prev.map((card) => ({
            ...card,
            value: last30.totals[card.id] ?? 0,
            prevValue: prev30.totals[card.id] ?? 0,
            data: last30.series[card.id] ?? [], // per-day last 30 days
          })),
        );
      } catch (err) {
        console.error('Failed to fetch 30 days data:', err);
      }
    }

    fetchData();
  }, []);

  useEffect(() => {
    if (!enabled) {
      setIsLoadingLiveCount(false);
      return;
    }
    let unsubscribe;
    let cancelled = false;

    setIsLoadingLiveCount(true);

    (async () => {
      try {
        const result = await subscribeToLiveProbeRequestCount(
          devices,
          setLiveCount,
        );

        if (cancelled) {
          result.unsubscribe();
          return;
        }

        setInitialCount(result.initialCount);
        unsubscribe = result.unsubscribe;
      } catch (err) {
        console.error('Failed to subscribe to live probe count:', err);
      } finally {
        if (!cancelled) {
          setIsLoadingLiveCount(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (unsubscribe) unsubscribe();
    };
  }, [enabled]);

  // useEffect(() => {
  //   fetchTotalStats().then((stats) => {
  //     if (!stats) return;

  //     setDataTotal((prev) =>
  //       prev.map((card) => ({
  //         ...card,
  //         value: stats[card.id]?.toLocaleString() ?? '0',
  //       })),
  //     );
  //   });
  // }, []);

  useEffect(() => {
    async function fetchData() {
      try {
        // Totals are needed here as it contains unique totals.
        // Cannot use reduce on serises data as totals will not be unique across all time.
        const [total, dataSeriesTotal] = await Promise.all([
          fetchTotalStats(),
          fetchAllDataSeries(),
        ]);
        setTotalDataSeriesDates(dataSeriesTotal.dayCounts);
        // Update the data array
        setDataTotal((prev) =>
          prev.map((card) => ({
            ...card,
            value: total[card.id] ?? 0,
            data: dataSeriesTotal[card.id] ?? [],
          })),
        );
        setIsLoadingTotalStats(false);
      } catch (err) {
        console.error('Failed to fetch data for all days:', err);
      }
    }
    setIsLoadingTotalStats(true);
    fetchData();
  }, []);

  // Lazily loaded when the manufacturer accordion is expanded so the single API
  // call (feeding both the table and the map) only fires when the user opens it.
  async function loadManufacturers() {
    try {
      setIsLoadingManufacturers(true);
      const manufacturersData = await fetchManufacturersData();
      const sortedData = [...manufacturersData].sort(
        (a, b) => Number(b.count ?? 0) - Number(a.count ?? 0),
      );
      setManufacturers(sortedData);
    } catch (err) {
      console.error('Failed to fetch manufacturers data:', err);
    } finally {
      setIsLoadingManufacturers(false);
    }
  }

  // Lazily loaded when the Sankey accordion is expanded.
  async function loadSankeyData() {
    try {
      const data = await fetchSankeyData();
      setSankeyData(data);
    } catch (err) {
      console.error('Failed to fetch sankey data:', err);
    }
  }

  function handleManufacturerAccordionChange(_, expanded) {
    setIsManufacturerExpanded(expanded);
    if (expanded && !hasFetchedManufacturers.current) {
      hasFetchedManufacturers.current = true;
      loadManufacturers();
    }
  }

  function handleSankeyExpand() {
    if (!hasFetchedSankey.current) {
      hasFetchedSankey.current = true;
      loadSankeyData();
    }
  }

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      {/* cards */}
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Overview
      </Typography>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{ mb: (theme) => theme.spacing(2) }}
      >
        {dataLast30Days.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard {...card} />
          </Grid>
        ))}
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            title="Probe Requests"
            value={initialCount}
            trend="up"
            interval={'Live'}
            hideSparkLineChart={true}
            hideTrendValues={true}
            liveValue={liveCount}
            liveFeed={enabled}
            isLoading={enabled && isLoadingLiveCount}
          />
        </Grid>
        {dataTotal.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard
              {...card}
              hideTrendValues={true}
              dayCount={totalDataSeriesDates}
              isLoading={isLoadingTotalStats}
            />
          </Grid>
        ))}
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <HighlightedCard />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SessionsChart probeSeries={probeSeriesPerDevice} />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <CapturedDataBarChart />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <MultiSeriesRadarChart totalsPerDeviceData={perDeviceTotalData} />
        </Grid>
      </Grid>
      <Accordion
        sx={{ mb: (theme) => theme.spacing(2) }}
        expanded={isManufacturerExpanded}
        onChange={handleManufacturerAccordionChange}
        slotProps={{
          transition: {
            unmountOnExit: true,
            onEntered: () => setIsManufacturerEntered(true),
            onExited: () => setIsManufacturerEntered(false),
          },
        }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography component="h2" variant="h6">
            Manufacturer data
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Based on the MAC addresses of devices captured at CERN, the
            following represents the manufacturers most frequently observed
            among the recorded devices.
          </Typography>
          <ManufacturerDataGrid
            manufacturers={manufacturers}
            loading={isLoadingManufacturers}
            mapReady={isManufacturerEntered}
          />
        </AccordionDetails>
      </Accordion>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Devices
      </Typography>

      <Grid container spacing={2} columns={3}>
        <Grid size={{ xs: 12, lg: 3 }}>
          <CustomizedDataGrid
            totalsPerDeviceData={perDeviceTotalData}
            probeSeries={probeSeriesPerDevice}
            sankeyData={sankeyData}
            onSankeyExpand={handleSankeyExpand}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
