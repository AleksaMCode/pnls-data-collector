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
  getDeviceGridColumns,
  rows as defaultRows,
} from '../../internals/data/gridData';
import { useMemo, useState } from 'react';
import { fetchDeviceOnlineStatus } from '../../firebase/firebase';
import CustomSankeyDiagram from './CustomSankeyDiagram';
import DeviceHeatMap from './DeviceHeatMap';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';

const EMPTY_STATUS = {};

function getWorkingStatus(status) {
  const now = new Date();

  const hour = Number(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Paris',
      hour: '2-digit',
      hour12: false,
    }).format(now),
  );

  // return status === 'Online' && hour >= 7 && hour < 18 ? 'Working' : 'Off';
  return status === 'Online' ? 'Working' : 'Off';
}

export default function CustomizedDataGrid({
  totalsPerDeviceData,
  probeSeries,
  sankeyData,
  onSankeyExpand,
}) {
  const { t } = useTranslation();
  const [isSankeyExpanded, setIsSankeyExpanded] = useState(false);
  const [isHeatMapExpanded, setIsHeatMapExpanded] = useState(true);
  const [showExpandTooltip, setShowExpandTooltip] = useState(false);
  const columns = getDeviceGridColumns(t);
  const onlineStatusQuery = useQuery({
    queryKey: ['device-online-status'],
    queryFn: fetchDeviceOnlineStatus,
    refetchInterval: 10 * 60 * 1000,
  });
  const onlineStatus = onlineStatusQuery.data ?? EMPTY_STATUS;

  const rows = useMemo(() => {
    if (!totalsPerDeviceData || !probeSeries) return defaultRows;

    return defaultRows.map((row) => {
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

        location: totals?.location ?? row.location,

        trend:
          Array.isArray(trendSeries) && trendSeries.length > 0
            ? trendSeries
            : row.trend,
      };
    });
  }, [totalsPerDeviceData, probeSeries, onlineStatus]);

  return (
    <Box>
      <DataGrid
        checkboxSelection={false}
        rows={rows}
        columns={columns}
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
          if (expanded && onSankeyExpand) {
            onSankeyExpand();
          }
        }}
      >
        <Tooltip
          title={t('customizedGrid.expandSankey')}
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
              {t('customizedGrid.sankeyTitle')}
            </Typography>
          </AccordionSummary>
        </Tooltip>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('customizedGrid.sankeyDescription')}
          </Typography>
          <Paper sx={{ p: 2 }}>
            <CustomSankeyDiagram sankeyData={sankeyData} />
          </Paper>
        </AccordionDetails>
      </Accordion>

      <Accordion
        sx={{ mt: 2 }}
        expanded={isHeatMapExpanded}
        onChange={(_, expanded) => {
          setIsHeatMapExpanded(expanded);
        }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2">
            {t('customizedGrid.heatmapTitle')}
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('customizedGrid.heatmapDescription')}
          </Typography>
          <Paper sx={{ p: 2 }}>
            <DeviceHeatMap totalsPerDeviceData={totalsPerDeviceData} />
          </Paper>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
