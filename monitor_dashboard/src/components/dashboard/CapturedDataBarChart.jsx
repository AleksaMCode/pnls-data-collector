import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import { BarChart } from '@mui/x-charts/BarChart';
import { useTheme } from '@mui/material/styles';
import { fetchMonthlyTotalsAllDevices } from '../../statsApi/StatsApi';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { getLocale } from '../../i18nLocale';
import { useQuery } from '@tanstack/react-query';

function formatMonthKeyToLabel(monthKey, locale) {
  const [yearStr, monthStr] = String(monthKey).split('-');
  const year = Number(yearStr);
  const month = Number(monthStr);

  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    month < 1 ||
    month > 12
  ) {
    return String(monthKey);
  }

  const date = new Date(year, month - 1, 1);
  const monthName = date
    .toLocaleString(locale, { month: 'short' })
    .toLowerCase();
  const yearShort = String(year).slice(-2);
  return `${monthName}-${yearShort}`;
}

export default function CapturedDataBarChart() {
  const { t, i18n } = useTranslation();
  const locale = getLocale(i18n.resolvedLanguage);
  const theme = useTheme();
  const colorPalette = [
    (theme.vars || theme).palette.primary.dark,
    (theme.vars || theme).palette.primary.main,
    (theme.vars || theme).palette.primary.light,
  ];

  const monthlyTotalsQuery = useQuery({
    queryKey: ['monthly-totals-all-devices'],
    queryFn: fetchMonthlyTotalsAllDevices,
  });

  const { months, monthCount, totalProbeCount, series } = useMemo(() => {
    const monthlyTotals = monthlyTotalsQuery.data ?? {};
    const monthKeys = Object.keys(monthlyTotals); // e.g. ['2025-01', '2025-02', ...]

    const nextMonths = monthKeys.map((monthKey) =>
      formatMonthKeyToLabel(monthKey, locale),
    );

    const probeData = [];
    const ssidData = [];
    const macData = [];

    monthKeys.forEach((month) => {
      const monthData = monthlyTotals[month] || {};
      probeData.push(monthData.probe_requests ?? 0);
      ssidData.push(monthData.ssid ?? 0);
      macData.push(monthData.mac ?? 0);
    });

    return {
      months: nextMonths,
      monthCount: monthKeys.length,
      totalProbeCount: probeData.reduce((acc, curr) => acc + curr, 0),
      series: [
        {
          id: 'probe-requests',
          label: t('common.probeRequests'),
          data: probeData,
        },
        { id: 'ssid', label: t('common.ssids'), data: ssidData },
        { id: 'mac', label: 'MAC', data: macData },
      ],
    };
  }, [locale, monthlyTotalsQuery.data, t]);
  return (
    <Card variant="outlined" sx={{ width: '100%' }}>
      <CardContent>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          {t('sections.capturedInformation')}
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
            {t('sections.capturedLastMonths', { count: monthCount })}
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
