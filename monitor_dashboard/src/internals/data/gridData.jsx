import { Tooltip } from '@mui/material';
import Avatar from '@mui/material/Avatar';
import Chip from '@mui/material/Chip';

import { SparkLineChart } from '@mui/x-charts/SparkLineChart';
import { getLastNDays } from '../../components/dashboard/StatCard';

function getDaysInMonth(month, year) {
  const date = new Date(year, month, 0);
  const monthName = date.toLocaleDateString('en-US', {
    month: 'short',
  });
  const daysInMonth = date.getDate();
  const days = [];
  let i = 1;
  while (days.length < daysInMonth) {
    days.push(`${monthName} ${i}`);
    i += 1;
  }
  return days;
}

function renderSparklineCell(params) {
  // const data = getDaysInMonth(4, 2024);
  const data = getLastNDays(30);
  const { value, colDef } = params;

  if (!value || value.length === 0) {
    return null;
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      <SparkLineChart
        data={value}
        width={colDef.computedWidth || 100}
        height={32}
        plotType="bar"
        showHighlight
        showTooltip
        color="hsl(210, 98%, 42%)"
        xAxis={{
          scaleType: 'band',
          data,
        }}
      />
    </div>
  );
}

function renderStatus(status) {
  const colors = {
    Online: 'success',
    Offline: 'default',
    Working: 'info',
    Off: 'secondary',
  };

  return <Chip label={status} color={colors[status]} size="small" />;
}

function getWorkingStatus() {
  const now = new Date();

  const hour = Number(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Paris',
      hour: '2-digit',
      hour12: false,
    }).format(now),
  );

  return hour >= 7 && hour < 18 ? 'Working' : 'Off';
}

export function renderAvatar(params) {
  if (params.value == null) {
    return '';
  }

  return (
    <Avatar
      sx={{
        backgroundColor: params.value.color,
        width: '24px',
        height: '24px',
        fontSize: '0.85rem',
      }}
    >
      {params.value.name.toUpperCase().substring(0, 1)}
    </Avatar>
  );
}

export const columns = [
  {
    field: 'device',
    headerName: 'Device',
    flex: 0.8,
    minWidth: 80,
    renderHeader: () => (
      <Tooltip title="Device's name">
        <span>Device</span>
      </Tooltip>
    ),
  },
  {
    field: 'status',
    headerName: 'Status',
    flex: 0.8,
    minWidth: 80,
    renderHeader: () => (
      <Tooltip title='Device is online if it was "seen" in the last 10 minutes.'>
        <span>Status</span>
      </Tooltip>
    ),
    renderCell: (params) => renderStatus(params.value),
  },
  // Device is capturing between 7 AM and 6 PM (Working status), otherwise Off
  {
    field: 'capturing',
    headerName: 'Capturing',
    flex: 0.8,
    minWidth: 80,
    renderHeader: () => (
      <Tooltip title="Device is capturing between 7 AM and 6 PM (has status `Working`).">
        <span>Capturing</span>
      </Tooltip>
    ),
    renderCell: (params) => renderStatus(params.value),
  },
  {
    field: 'probeRequestCount',
    headerName: 'Probe Request',
    headerAlign: 'right',
    align: 'right',
    flex: 1,
    minWidth: 80,
    renderHeader: () => (
      <Tooltip title="Total amount of captured Probe Requests for the device.">
        <span>Probe Request</span>
      </Tooltip>
    ),
  },
  {
    field: 'ssidCount',
    headerName: 'SSID',
    headerAlign: 'right',
    align: 'right',
    flex: 0.8,
    minWidth: 100,
    renderHeader: () => (
      <Tooltip title="Total amount of captured SSIDs for the device.">
        <span>SSID</span>
      </Tooltip>
    ),
  },
  {
    field: 'macCount',
    headerName: 'MAC',
    headerAlign: 'right',
    align: 'right',
    flex: 0.8,
    minWidth: 120,
    renderHeader: () => (
      <Tooltip title="Total amount of captured MAC addresses for the device.">
        <span>MAC</span>
      </Tooltip>
    ),
  },
  {
    field: 'location',
    headerName: 'Location',
    headerAlign: 'right',
    align: 'right',
    flex: 1,
    minWidth: 300,
    renderHeader: () => (
      <Tooltip title="Location of the devie inside of CERN.">
        <span>Location</span>
      </Tooltip>
    ),
  },
  {
    field: 'trend',
    headerName: 'Daily capture',
    flex: 1,
    minWidth: 150,
    renderHeader: () => (
      <Tooltip title="Daily capture for the last 30 days.">
        <span>Daily capture</span>
      </Tooltip>
    ),
    renderCell: renderSparklineCell,
  },
];

export const rows = [
  {
    id: 1,
    device: 'RPI-1',
    status: 'Online',
    capturing: 'Working',
    ssidCount: 8345,
    probeRequestCount: 212423,
    macCount: 18.5,
    location: "Users Office's waiting room  (61/R-202)",
    trend: [
      469172, 488506, 592287, 617401, 640374, 632751, 668638, 807246, 749198,
      944863, 911787, 844815, 992022, 1143838, 1446926, 1267886, 1362511,
      1348746, 1560533, 1670690, 1695142, 1916613, 1823306, 1683646, 2025965,
      2529989, 3263473, 3296541, 3041524, 2599497,
    ],
  },
  {
    id: 2,
    device: 'RPI-2',
    status: 'Online',
    capturing: 'Working',
    ssidCount: 5653,
    probeRequestCount: 172240,
    macCount: 9.7,
    location: 'CERN Community Support Centres',
    trend: [
      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
      0, 557488, 1341471, 2044561, 2206438,
    ],
  },
  {
    id: 3,
    device: 'RPI-3',
    status: 'Online',
    capturing: 'Working',
    ssidCount: 3455,
    probeRequestCount: 58240,
    macCount: 15.2,
    location: "Stefan's office (31 R-009)",
    // This is just placeholder data
    trend: [
      166896, 190041, 248686, 226746, 261744, 271890, 332176, 381123, 396435,
      495620, 520278, 460839, 704158, 559134, 681089, 712384, 765381, 771374,
      851314, 907947, 903675, 1049642, 1003160, 881573, 1072283, 1139115,
      1382701, 1395655, 1355040, 1381571,
    ],
  },
];
