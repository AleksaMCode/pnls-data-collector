import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import { BarChart } from '@mui/x-charts/BarChart';
import { useTheme } from '@mui/material/styles';
import { fetchMonthlyTotalsAllDevices } from '../../statsApi/StatsApi';
import { useEffect, useState } from 'react';

function getLastNMonths(n) {
  const result = [];
  const now = new Date();

  for (let i = n - 1; i >= 0; i--) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1);

    const monthName = date.toLocaleString('en-US', {
      month: 'short',
    });

    result.push(monthName);
  }

  return result;
}

export default function CapturedDataBarChart() {
  const theme = useTheme();

  const [months, setMonths] = useState([]);
  const [monthCount, setMonthCount] = useState(0);
  const [totalProbeCount, setTotalProbeCount] = useState(0);
  const colorPalette = [
    (theme.vars || theme).palette.primary.dark,
    (theme.vars || theme).palette.primary.main,
    (theme.vars || theme).palette.primary.light,
  ];

  const [series, setSeries] = useState([]);

  // useEffect(() => {
  //   fetchMonthlyTotalsAllDevices()
  //     .then((data) => {
  //       const probe = [];
  //       const ssid = [];
  //       const mac = [];
  //       const monthKeys = Object.keys(data)
  //       setMonthCount(monthKeys.length)
  //       setMonths(getLastNMonths(monthKeys.length));

  //       const computedSeries = monthKeys.map((month) => ({
  //       data: [
  //         data[month].probe_requests ?? 0,
  //         data[month].ssid ?? 0,
  //         data[month].mac ?? 0,
  //       ],
  //     }));

  //     setSeries(computedSeries);
  //     })
  //     .catch(console.error);
  // }, []);

  //   useEffect(() => {
  //   fetchMonthlyTotalsAllDevices()
  //     .then((data) => {
  //       const probe = [];
  //       const ssid = [];
  //       const mac = [];
  //       setMonthCount(Object.keys(data).length)
  //       setMonths(getLastNMonths(monthC));

  //       Object.values(data).forEach((month) => {
  //         probe.push(month.probe_requests ?? 0);
  //         ssid.push(month.ssid ?? 0);
  //         mac.push(month.mac ?? 0);
  //       });

  //       setSeries([
  //         {
  //           id: 'probe-requests',
  //           label: 'Probe requests',
  //           data: probe,
  //           stack: 'A',
  //         },
  //         { id: 'ssid', label: 'SSID', data: ssid, stack: 'A' },
  //         { id: 'mac', label: 'MAC', data: mac, stack: 'A' },
  //       ]);
  //     })
  //     .catch(console.error);
  // }, []);

  useEffect(() => {
    fetchMonthlyTotalsAllDevices()
      .then((data) => {
        const monthKeys = Object.keys(data); // e.g. ['2025-01', '2025-02', ...]
        setMonthCount(monthKeys.length);
        setMonths(getLastNMonths(monthKeys.length));

        // Prepare separate series for each metric
        const probeData = [];
        const ssidData = [];
        const macData = [];

        monthKeys.forEach((month) => {
          const monthData = data[month] || {};
          probeData.push(monthData.probe_requests ?? 0);
          ssidData.push(monthData.ssid ?? 0);
          macData.push(monthData.mac ?? 0);
        });

        const computedSeries = [
          { id: 'probe-requests', label: 'Probe requests', data: probeData },
          { id: 'ssid', label: 'SSID', data: ssidData },
          { id: 'mac', label: 'MAC', data: macData },
        ];

        const totalProbe = probeData.reduce((acc, curr) => acc + curr, 0);
        setTotalProbeCount(totalProbe);

        setSeries(computedSeries);
      })
      .catch(console.error);
  }, []);
  return (
    <Card variant="outlined" sx={{ width: '100%' }}>
      <CardContent>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          Captured information
        </Typography>
        <Stack sx={{ justifyContent: 'space-between' }}>
          <Stack
            direction="row"
            sx={{
              alignContent: { xs: 'center', sm: 'flex-start' },
              alignItems: 'center',
              gap: 1,
            }}
          >
            <Typography variant="h4" component="p">
              {totalProbeCount.toLocaleString()}
            </Typography>
          </Stack>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Captured information for the last {monthCount} months
          </Typography>
        </Stack>
        <BarChart
          borderRadius={8}
          colors={colorPalette}
          xAxis={[
            {
              scaleType: 'band',
              categoryGapRatio: 0.5,
              data: months,
              height: 24,
            },
          ]}
          yAxis={[{ width: 65 }]}
          series={series}
          height={250}
          margin={{ left: 0, right: 0, top: 20, bottom: 0 }}
          grid={{ horizontal: true }}
          hideLegend
        />
      </CardContent>
    </Card>
  );
}
