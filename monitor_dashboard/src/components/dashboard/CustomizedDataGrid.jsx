import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { DataGrid } from '@mui/x-data-grid';
import {
  columns as defaultColumns,
  rows as defaultRows,
} from '../../internals/data/gridData';
import { useEffect, useState } from 'react';
import { fetchDeviceOnlineStatus } from '../../firebase/firebase';
import CustomSankeyDiagram from './CustomSankeyDiagram';

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
  sankeyData,
}) {
  const [rows, setRows] = useState(defaultRows);
  const [onlineStatus, setOnlineStatus] = useState({});
  const [isSankeyExpanded, setIsSankeyExpanded] = useState(false);
  const [showExpandTooltip, setShowExpandTooltip] = useState(false);

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
    <Box>
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

      <Accordion
        sx={{ mt: 2 }}
        expanded={isSankeyExpanded}
        onChange={(_, expanded) => {
          setIsSankeyExpanded(expanded);
          setShowExpandTooltip(false);
        }}
      >
        <Tooltip
          title="Click to expand and see the Sankey diagram"
          arrow
          open={!isSankeyExpanded && showExpandTooltip}
          onOpen={() => setShowExpandTooltip(true)}
          onClose={() => setShowExpandTooltip(false)}
          disableHoverListener={isSankeyExpanded}
          disableFocusListener
          disableTouchListener
          disableInteractive
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">
              Device to Manufacturer to Country (Sankey)
            </Typography>
          </AccordionSummary>
        </Tooltip>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            This Sankey view shows only the top 20 manufacturers from each
            device.
          </Typography>
          <Paper sx={{ p: 2 }}>
            <CustomSankeyDiagram sankeyData={sankeyData} />
          </Paper>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
