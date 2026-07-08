import { useTheme } from '@mui/material/styles';
import PropTypes from 'prop-types';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import { areaElementClasses } from '@mui/x-charts/LineChart';
import { useEffect, useState } from 'react';
import { CircularProgress, Fade } from '@mui/material';

/**
 *
 * @param {*} value Current value (e.g., last 30 days)
 * @param {*} prevValue Previous value (e.g., previous 30 days)
 * @param {*} tolerance Tolarance in percentage for neutral trend
 * @returns
 */
function calculateTrend(value, prevValue, tolerance = 0.1) {
  if (prevValue === 0 || prevValue == null || value == null) {
    return {
      trend: 'neutral',
      deltaPercent: '0%',
    };
  }

  const diff = value - prevValue;
  const percentChange = diff / prevValue;

  const deltaPercent = `${percentChange >= 0 ? '+' : ''}${(
    percentChange * 100
  ).toFixed(1)}%`;

  if (percentChange > 0) {
    return {
      trend: 'up',
      deltaPercent,
    };
  }

  // Keep tolerance only for negative values.
  if (percentChange < 0 && Math.abs(percentChange) < tolerance) {
    return {
      trend: 'neutral',
      deltaPercent,
    };
  }

  return {
    trend: percentChange < 0 ? 'down' : 'neutral',
    deltaPercent,
  };
}

export function getLastNDays(
  n = 30,
  locale = 'en-US',
  timeZone = 'Europe/Paris',
) {
  const days = [];
  const today = new Date();

  for (let i = n; i > 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);

    const monthName = d.toLocaleDateString(locale, {
      month: 'short',
      timeZone,
    });
    const dayNumber = d.getDate();
    days.push(`${monthName} ${dayNumber}`);
  }

  return days;
}

function AreaGradient({ color, id }) {
  return (
    <defs>
      <linearGradient id={id} x1="50%" y1="0%" x2="50%" y2="100%">
        <stop offset="0%" stopColor={color} stopOpacity={0.3} />
        <stop offset="100%" stopColor={color} stopOpacity={0} />
      </linearGradient>
    </defs>
  );
}

AreaGradient.propTypes = {
  color: PropTypes.string.isRequired,
  id: PropTypes.string.isRequired,
};

function StatCard({
  title,
  value,
  prevValue,
  interval,
  trend,
  data,
  hideSparkLineChart,
  hideTrendValues,
  liveValue = 0,
  liveFeed = false,
  dayCount = 30,
  isLoading = false,
}) {
  const theme = useTheme();
  const daysInWeek = getLastNDays(dayCount);
  const [displayValue, setDisplayValue] = useState(value);
  const [livePercentage, setLivePercentage] = useState(0);
  const [computedTrend, setComputedTrend] = useState(trend);
  const [deltaPercent, setDeltaPercent] = useState(0);

  const trendColors = {
    up:
      theme.palette.mode === 'light'
        ? theme.palette.success.main
        : theme.palette.success.dark,
    down:
      theme.palette.mode === 'light'
        ? theme.palette.error.main
        : theme.palette.error.dark,
    neutral:
      theme.palette.mode === 'light'
        ? theme.palette.grey[400]
        : theme.palette.grey[700],
  };

  const labelColors = {
    up: 'success',
    down: 'error',
    neutral: 'default',
  };

  const color = labelColors[computedTrend];
  const chartColor = trendColors[computedTrend];

  useEffect(() => {
    if (trend) {
      setComputedTrend(trend);
    } else {
      const { trend, deltaPercent } = calculateTrend(value, prevValue);
      setComputedTrend(trend);
      setDeltaPercent(deltaPercent);
    }
  }, [value, prevValue]);

  // -3 on live value is a quickfix for live values.
  // When the button is toggled the values get reseted.
  useEffect(() => {
    if (!liveFeed) {
      return;
    }

    if (liveFeed && value > 0 && liveValue - 3 > value) {
      const nextValue = liveValue - 3;
      setDisplayValue(nextValue);
      setLivePercentage(((nextValue - value) / value) * 100);
    } else if (!liveFeed) {
      setDisplayValue(0);
    }
  }, [liveValue, liveFeed, value]);

  return (
    <Card variant="outlined" sx={{ height: '100%', flexGrow: 1 }}>
      <CardContent>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          {title}
        </Typography>
        <Stack
          direction="column"
          sx={{ justifyContent: 'space-between', flexGrow: '1', gap: 1 }}
        >
          <Stack sx={{ justifyContent: 'space-between' }}>
            <Stack
              direction="row"
              sx={{ justifyContent: 'space-between', alignItems: 'center' }}
            >
              {isLoading ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <CircularProgress size={24} />
                  {/* <Typography
                    variant="h4"
                    component="p"
                    sx={{ color: 'text.secondary' }}
                  >
                    Loading...
                  </Typography> */}
                </Box>
              ) : (
                <Fade direction="down" in timeout={300} key={displayValue}>
                  <Typography variant="h4" component="p">
                    {(liveValue - 3 > value && liveFeed
                      ? displayValue
                      : value
                    )?.toLocaleString()}
                  </Typography>
                </Fade>
              )}
              {!hideTrendValues && !isLoading && (
                <Chip size="small" color={color} label={deltaPercent} />
              )}
              {liveValue - 3 > value && liveFeed && !isLoading && (
                <Chip
                  size="small"
                  color={color}
                  label={`+${livePercentage.toFixed(2)}%`}
                />
              )}
            </Stack>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {interval}
            </Typography>
          </Stack>
          {!hideSparkLineChart && data && !isLoading && (
            <Box sx={{ width: '100%', height: 50 }}>
              <Fade direction="down" in timeout={300} key={data}>
                <SparkLineChart
                  color={chartColor}
                  data={data}
                  area
                  showHighlight
                  showTooltip
                  xAxis={{
                    scaleType: 'band',
                    data: daysInWeek, // Use the correct property 'data' for xAxis
                  }}
                  sx={{
                    [`& .${areaElementClasses.root}`]: {
                      fill: `url(#area-gradient-${value})`,
                    },
                  }}
                >
                  <AreaGradient
                    color={chartColor}
                    id={`area-gradient-${value}`}
                  />
                </SparkLineChart>
              </Fade>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

StatCard.propTypes = {
  data: PropTypes.arrayOf(PropTypes.number).isRequired,
  interval: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  trend: PropTypes.oneOf(['down', 'neutral', 'up']).isRequired,
  value: PropTypes.string.isRequired,
};

export default StatCard;
