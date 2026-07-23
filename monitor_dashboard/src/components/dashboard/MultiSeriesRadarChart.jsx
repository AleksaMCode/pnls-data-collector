import { Box, Card, CardContent, Typography } from '@mui/material';
import { RadarChart } from '@mui/x-charts/RadarChart';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

export default function MultiSeriesRadarChart({ totalsPerDeviceData }) {
  const { t } = useTranslation();
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
          {t('sections.capturedInformation')}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {t('sections.deviceComparison')}
        </Typography>
        <Box height={6} />
        <RadarChart
          height={250}
          series={series}
          radar={{
            metrics: [
              t('deviceGrid.headers.probeRequest'),
              t('common.ssids'),
              'MAC',
            ],
          }}
        />
      </CardContent>
    </Card>
  );
}
