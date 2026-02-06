import { DataGrid } from '@mui/x-data-grid';
import {
  columns as defaultColumns,
  rows as defaultRows,
} from '../../internals/data/gridData';
import { useEffect, useState } from 'react';
import { fetchDeviceOnlineStatus } from '../../firebase/firebase';

function getWorkingStatus(status) {
  const now = new Date();

  const hour = Number(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Paris',
      hour: '2-digit',
      hour12: false,
    }).format(now),
  );

  return status === 'Online' && hour >= 7 && hour < 18 ? 'Working' : 'Off';
}

export default function CustomizedDataGrid({
  totalsPerDeviceData,
  probeSeries,
}) {
  const [rows, setRows] = useState(defaultRows);
  const [onlineStatus, setOnlineStatus] = useState({});

  useEffect(() => {
    if (!totalsPerDeviceData || !probeSeries) return;

    const rowsMapped = defaultRows.map((row) => {
      const totals = totalsPerDeviceData[row.device];
      const trendSeries = probeSeries[row.device];
      const status = onlineStatus[row.device] ? 'Online' : 'Offline';

      return {
        ...row,
        status: status,

        capturing: getWorkingStatus(status),

        probeRequestCount:
          totals?.probe_requests != null
            ? totals.probe_requests.toLocaleString()
            : row.probeRequestCount,

        ssidCount:
          totals?.ssid != null ? totals.ssid.toLocaleString() : row.ssidCount,

        macCount:
          totals?.mac != null ? totals.mac.toLocaleString() : row.macCount,

        trend:
          Array.isArray(trendSeries) && trendSeries.length > 0
            ? trendSeries
            : row.trend,
      };
    });
    setRows(rowsMapped);
  }, [totalsPerDeviceData, probeSeries]);

  useEffect(() => {
    const updateStatus = async () => {
      try {
        const statusMap = await fetchDeviceOnlineStatus();
        setOnlineStatus(statusMap);
      } catch (err) {
        console.error('Failed to fetch device status', err);
      }
    };

    updateStatus();

    // Check online status every 10 minutes
    const interval = setInterval(updateStatus, 10 * 60 * 1000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  return (
    <DataGrid
      checkboxSelection={false}
      rows={rows}
      columns={defaultColumns}
      getRowClassName={(params) =>
        params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
      }
      initialState={{
        pagination: { paginationModel: { pageSize: 20 } },
      }}
      pageSizeOptions={[10, 20, 50]}
      disableColumnResize
      density="compact"
      slotProps={{
        filterPanel: {
          filterFormProps: {
            logicOperatorInputProps: {
              variant: 'outlined',
              size: 'small',
            },
            columnInputProps: {
              variant: 'outlined',
              size: 'small',
              sx: { mt: 'auto' },
            },
            operatorInputProps: {
              variant: 'outlined',
              size: 'small',
              sx: { mt: 'auto' },
            },
            valueInputProps: {
              InputComponentProps: {
                variant: 'outlined',
                size: 'small',
              },
            },
          },
        },
      }}
    />
  );
}
