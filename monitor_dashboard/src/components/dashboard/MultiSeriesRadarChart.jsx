import { Box, Card, CardContent, Typography } from '@mui/material';
import { RadarChart } from '@mui/x-charts/RadarChart';
import { useEffect, useState } from 'react';

export default function MultiSeriesRadarChart({ totalsPerDeviceData }) {
  const [series, setSeries] = useState([]);

  useEffect(() => {
    if (!totalsPerDeviceData) {
      setSeries([]);
      return;
    }

    const computedSeries = Object.entries(totalsPerDeviceData).map(
      ([device, counts]) => ({
        label: device,
        data: [counts.probe_requests, counts.ssid, counts.mac],
        valueFormatter: (val) => val.toLocaleString(),
      }),
    );

    setSeries(computedSeries);
  }, [totalsPerDeviceData]);

  return (
    <Card variant="outlined" sx={{ width: '100%' }}>
      <CardContent>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          Captured information
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Data comparison between capturing devices
        </Typography>
        <Box height={6} />
        <RadarChart
          height={250}
          series={series}
          radar={{
            metrics: ['Probe request', 'SSID', 'MAC'],
          }}
        />
      </CardContent>
    </Card>
  );
}
