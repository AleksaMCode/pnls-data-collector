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
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { subscribeToLiveProbeRequestCount } from '../../firebase/firebase';
import {
  fetchAverageDailyCounts,
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
import { useTranslation } from 'react-i18next';

const data = [
  {
    id: 'probeRequestCount',
    titleKey: 'common.probeRequests',
    value: 0,
    prevValue: 0,
    intervalKey: 'mainGrid.last30Days',
    data: [
      200, 24, 220, 260, 240, 380, 100, 240, 280, 240, 300, 340, 320, 360, 340,
      380, 360, 400, 380, 420, 400, 640, 340, 460, 440, 480, 460, 600, 880, 920,
    ],
  },
  {
    id: 'ssidCount',
    titleKey: 'common.ssids',
    value: 0,
    prevValue: 0,
    intervalKey: 'mainGrid.last30Days',
    data: [
      1640, 1250, 970, 1130, 1050, 900, 720, 1080, 900, 450, 920, 820, 840, 600,
      820, 780, 800, 760, 380, 740, 660, 620, 840, 500, 520, 480, 400, 360, 300,
      220,
    ],
  },
  {
    id: 'macCount',
    titleKey: 'common.macAddresses',
    value: 0,
    prevValue: 0,
    intervalKey: 'mainGrid.last30Days',
    data: [
      500, 400, 510, 530, 520, 600, 530, 520, 510, 730, 520, 510, 530, 620, 510,
      530, 520, 410, 530, 520, 610, 530, 520, 610, 530, 420, 510, 430, 520, 510,
    ],
  },
];

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
    intervalKey: 'mainGrid.totalUnique',
    trend: 'up',
    data: [],
  },
  {
    id: 'macCount',
    titleKey: 'common.macAddresses',
    value: 0,
    intervalKey: 'mainGrid.totalUnique',
    trend: 'up',
    data: [],
  },
];

const averageDailyTemplate = [
  {
    id: 'probeRequestCount',
    titleKey: 'common.probeRequests',
    value: 0,
    intervalKey: 'mainGrid.averagePerDay',
    trend: 'up',
    data: [],
  },
  {
    id: 'ssidCount',
    titleKey: 'common.ssids',
    value: 0,
    intervalKey: 'mainGrid.averagePerDay',
    trend: 'up',
    data: [],
  },
  {
    id: 'macCount',
    titleKey: 'common.macAddresses',
    value: 0,
    intervalKey: 'mainGrid.averagePerDay',
    trend: 'up',
    data: [],
  },
];

export default function MainGrid() {
  const { t } = useTranslation();
  // Initial count for Probe Requsts
  const [initialCount, setInitialCount] = useState(0);
  // Live count of Probe Requests
  const [liveCount, setLiveCount] = useState(0);
  const [isLoadingLiveCount, setIsLoadingLiveCount] = useState(false);
  // TODO Store devices somewhere else or better yet fetch from Firebase device names
  const devices = ['RPI-1', 'RPI-2', 'RPI-3'];
  const { enabled } = useLiveCount();
  const [isManufacturerExpanded, setIsManufacturerExpanded] = useState(false);
  const [shouldLoadManufacturers, setShouldLoadManufacturers] = useState(false);
  const [shouldLoadSankey, setShouldLoadSankey] = useState(false);
  // Only render the heavy world map once the accordion has finished expanding,
  // so the open/close animation stays smooth.
  const [isManufacturerEntered, setIsManufacturerEntered] = useState(false);

  const probeSeriesPerDeviceQuery = useQuery({
    queryKey: ['probe-requests-per-device', 30],
    queryFn: () => fetchProbeRequestsPerDeviceLastNDays(30),
  });

  const totalPerDeviceQuery = useQuery({
    queryKey: ['total-per-device-stats'],
    queryFn: fetchTotalPerDeviceStats,
  });

  const last30VsPrev30Query = useQuery({
    queryKey: ['last-30-vs-prev-30'],
    queryFn: async () => {
      const [last30, prev30] = await Promise.all([
        fetchLast30DaysTotalsWithSeries(),
        fetchPrevious30DaysTotals(),
      ]);

      return { last30, prev30 };
    },
  });

  const totalOverviewQuery = useQuery({
    queryKey: ['total-overview-series-average'],
    queryFn: async () => {
      const [total, dataSeriesTotal, averageDaily] = await Promise.all([
        fetchTotalStats(),
        fetchAllDataSeries(),
        fetchAverageDailyCounts(),
      ]);

      return { total, dataSeriesTotal, averageDaily };
    },
  });

  const manufacturersQuery = useQuery({
    queryKey: ['manufacturers'],
    queryFn: async () => {
      const manufacturersData = await fetchManufacturersData();
      return [...manufacturersData].sort(
        (a, b) => Number(b.count ?? 0) - Number(a.count ?? 0),
      );
    },
    enabled: shouldLoadManufacturers,
  });

  const sankeyQuery = useQuery({
    queryKey: ['sankey-data'],
    queryFn: fetchSankeyData,
    enabled: shouldLoadSankey,
  });

  const dataLast30Days = useMemo(() => {
    const last30 = last30VsPrev30Query.data?.last30;
    const prev30 = last30VsPrev30Query.data?.prev30;

    if (!last30 || !prev30) {
      return data;
    }

    return data.map((card) => ({
      ...card,
      value: last30.totals[card.id] ?? 0,
      prevValue: prev30.totals[card.id] ?? 0,
      data: last30.series[card.id] ?? [],
    }));
  }, [last30VsPrev30Query.data]);

  const dataTotal = useMemo(() => {
    const total = totalOverviewQuery.data?.total;
    const dataSeriesTotal = totalOverviewQuery.data?.dataSeriesTotal;

    if (!total || !dataSeriesTotal) {
      return dataTotalTemplate;
    }

    return dataTotalTemplate.map((card) => ({
      ...card,
      value: total[card.id] ?? 0,
      data: dataSeriesTotal[card.id] ?? [],
    }));
  }, [totalOverviewQuery.data]);

  const averageDailyData = useMemo(() => {
    const averageDaily = totalOverviewQuery.data?.averageDaily;

    if (!averageDaily) {
      return averageDailyTemplate;
    }

    return averageDailyTemplate.map((card) => ({
      ...card,
      value: averageDaily[card.id] ?? 0,
    }));
  }, [totalOverviewQuery.data]);

  const totalDataSeriesDates =
    totalOverviewQuery.data?.dataSeriesTotal?.dayCounts;
  const perDeviceTotalData = totalPerDeviceQuery.data ?? null;
  const probeSeriesPerDevice = probeSeriesPerDeviceQuery.data ?? null;
  const sankeyData = sankeyQuery.data ?? {};
  const manufacturers = manufacturersQuery.data ?? [];

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

  function handleManufacturerAccordionChange(_, expanded) {
    setIsManufacturerExpanded(expanded);
    if (expanded) {
      setShouldLoadManufacturers(true);
    }
  }

  function handleSankeyExpand() {
    setShouldLoadSankey(true);
  }

  return (
    <Box sx={{ width: '100%' }}>
      {/* cards */}
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        {t('mainGrid.overview')}
      </Typography>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{ mb: (theme) => theme.spacing(2) }}
      >
        {dataLast30Days.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard
              {...card}
              title={t(card.titleKey)}
              interval={t(card.intervalKey)}
            />
          </Grid>
        ))}
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            title={t('common.probeRequests')}
            value={initialCount}
            trend="up"
            interval={t('mainGrid.live')}
            hideSparkLineChart={true}
            hideTrendValues={true}
            liveValue={liveCount}
            liveFeed={enabled}
            isLoading={enabled && isLoadingLiveCount}
          />
        </Grid>
        {dataTotal.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 6, lg: 4 }}>
            <StatCard
              {...card}
              title={t(card.titleKey)}
              interval={t(card.intervalKey)}
              hideTrendValues={true}
              dayCount={totalDataSeriesDates}
              isLoading={totalOverviewQuery.isLoading}
            />
          </Grid>
        ))}
        {averageDailyData.map((card, index) => (
          <Grid key={index} size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard
              {...card}
              title={t(card.titleKey)}
              interval={t(card.intervalKey)}
              hideSparkLineChart={true}
              hideTrendValues={true}
              isLoading={totalOverviewQuery.isLoading}
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
            {t('mainGrid.manufacturerData')}
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('mainGrid.manufacturerDescription')}
          </Typography>
          <ManufacturerDataGrid
            manufacturers={manufacturers}
            loading={manufacturersQuery.isLoading}
            mapReady={isManufacturerEntered}
          />
        </AccordionDetails>
      </Accordion>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        {t('common.devices')}
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
