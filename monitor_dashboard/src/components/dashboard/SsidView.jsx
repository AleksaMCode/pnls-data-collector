import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import FormControl from '@mui/material/FormControl';
import OutlinedInput from '@mui/material/OutlinedInput';
import InputAdornment from '@mui/material/InputAdornment';
import { DataGrid } from '@mui/x-data-grid';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'react-toastify';
import { downloadSsidStatsCsv, fetchSsidStats } from '../../statsApi/StatsApi';
import { useTranslation } from 'react-i18next';
import { getLocale } from '../../i18nLocale';
import { useQuery } from '@tanstack/react-query';
import SsidGeoMap from './SsidGeoMap';

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 400;

// Fields the API supports server-side sorting on.
const SERVER_SORTABLE_FIELDS = new Set([
  'ssid',
  'seen_count',
  'first_seen',
  'last_seen',
  'has_geo',
]);

function formatDateTime(value, locale) {
  if (!value) {
    return '-';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  // English uses DD/MM/YYYY with a 12-hour clock instead of the US
  // month-first format, e.g. "23/11/2026, 03:45:12 PM".
  if (locale.startsWith('en')) {
    return parsed
      .toLocaleString('en-GB', {
        timeZone: 'Europe/Paris',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h12',
      })
      .toUpperCase();
  }

  return parsed.toLocaleString(locale, { timeZone: 'Europe/Paris' });
}

export default function SsidView() {
  const { t, i18n } = useTranslation();
  const locale = getLocale(i18n.resolvedLanguage);
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: PAGE_SIZE,
  });
  const [sortModel, setSortModel] = useState([
    { field: 'last_seen', sort: 'desc' },
  ]);

  const [isDownloadingCsv, setIsDownloadingCsv] = useState(false);
  const [selectedRowId, setSelectedRowId] = useState(null);

  const columns = useMemo(
    () => [
      {
        field: 'ssid',
        headerName: t('common.ssids'),
        // Takes the width left over by the fixed-width columns.
        flex: 1,
        minWidth: 240,
        renderCell: (params) => params.row.ssid || '-',
      },
      {
        field: 'seen_count',
        headerName: t('ssidView.seenCount'),
        type: 'number',
        width: 140,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) =>
          Number(params.row.seen_count ?? 0).toLocaleString(),
      },
      {
        field: 'first_seen',
        headerName: t('ssidView.firstSeen'),
        width: 210,
        renderCell: (params) => formatDateTime(params.row.first_seen, locale),
      },
      {
        field: 'last_seen',
        headerName: t('ssidView.lastSeen'),
        width: 210,
        renderCell: (params) => formatDateTime(params.row.last_seen, locale),
      },
      {
        field: 'has_geo',
        headerName: t('ssidView.hasGeo'),
        type: 'boolean',
        width: 130,
        // First click shows the SSIDs with a geolocation first.
        sortingOrder: ['desc', 'asc', null],
      },
    ],
    [locale, t],
  );

  // Debounce the search input: only fire once the user stops typing.
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);

    return () => clearTimeout(timeoutId);
  }, [searchInput]);

  // Reset to the first page whenever the search term changes.
  useEffect(() => {
    setPaginationModel((prev) => ({ ...prev, page: 0 }));
  }, [debouncedSearch]);

  const { sortBy, sortOrder } = useMemo(() => {
    const activeSort = sortModel[0];
    if (activeSort && SERVER_SORTABLE_FIELDS.has(activeSort.field)) {
      return {
        sortBy: activeSort.field,
        sortOrder: activeSort.sort ?? 'desc',
      };
    }
    return { sortBy: 'last_seen', sortOrder: 'desc' };
  }, [sortModel]);

  const ssidStatsQuery = useQuery({
    queryKey: [
      'ssid-stats',
      {
        search: debouncedSearch || '',
        sortBy,
        sortOrder,
        page: paginationModel.page,
        pageSize: paginationModel.pageSize,
      },
    ],
    queryFn: () =>
      fetchSsidStats({
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
        offset: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
      }),
    placeholderData: (previousData) => previousData,
  });

  const rows = useMemo(() => {
    const items = ssidStatsQuery.data?.items ?? [];
    return items.map((item, index) => ({
      id: `${item.ssid ?? 'ssid'}-${index}`,
      ssid: item.ssid,
      seen_count: item.seen_count,
      first_seen: item.first_seen,
      last_seen: item.last_seen,
      has_geo: Boolean(item.has_geo),
      geo: item.geo ?? null,
    }));
  }, [ssidStatsQuery.data]);

  const rowCount = ssidStatsQuery.data?.pagination?.total ?? 0;

  // Row ids are only unique within a page, so the selection is dropped
  // whenever a different set of rows is requested.
  useEffect(() => {
    setSelectedRowId(null);
  }, [debouncedSearch, sortBy, sortOrder, paginationModel]);

  const selectedRow = useMemo(
    () => rows.find((row) => row.id === selectedRowId) ?? null,
    [rows, selectedRowId],
  );

  const rowSelectionModel = useMemo(
    () => ({
      type: 'include',
      ids: new Set(selectedRowId == null ? [] : [selectedRowId]),
    }),
    [selectedRowId],
  );

  const mapHint = useMemo(() => {
    if (!selectedRow) {
      return t('ssidView.mapSelectHint');
    }
    const ssid = selectedRow.ssid || '-';
    if (!selectedRow.has_geo) {
      return t('ssidView.mapNoGeo', { ssid });
    }
    return t('ssidView.mapShowing', {
      ssid,
      count: selectedRow.geo?.length ?? 0,
    });
  }, [selectedRow, t]);

  useEffect(() => {
    if (!ssidStatsQuery.isError) {
      return;
    }

    console.error('Failed to fetch SSID stats:', ssidStatsQuery.error);
  }, [ssidStatsQuery.error, ssidStatsQuery.isError]);

  async function handleDownloadCsv() {
    setIsDownloadingCsv(true);
    try {
      const { blob, filename } = await downloadSsidStatsCsv({
        search: debouncedSearch || undefined,
        sortBy,
        sortOrder,
      });

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download =
        filename ?? `ssid_stats_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      toast.success(t('ssidView.downloadSuccess'));
    } catch (err) {
      console.error('Failed to download SSID CSV:', err);
      toast.error(t('ssidView.downloadError'));
    } finally {
      setIsDownloadingCsv(false);
    }
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        {t('common.ssids')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('ssidView.description')}
      </Typography>

      <Stack spacing={2}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          sx={{ alignItems: { xs: 'stretch', sm: 'center' } }}
        >
          <FormControl sx={{ width: '100%' }}>
            <OutlinedInput
              size="small"
              placeholder={t('common.searchSsid')}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              startAdornment={
                <InputAdornment position="start">
                  <SearchRoundedIcon fontSize="small" />
                </InputAdornment>
              }
            />
          </FormControl>

          <Button
            variant="outlined"
            onClick={handleDownloadCsv}
            disabled={isDownloadingCsv}
            startIcon={
              isDownloadingCsv ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <DownloadRoundedIcon fontSize="small" />
              )
            }
            sx={{ minWidth: 170, alignSelf: { xs: 'flex-start', sm: 'auto' } }}
          >
            {isDownloadingCsv
              ? t('common.downloading')
              : t('common.downloadCsv')}
          </Button>
        </Stack>
        {/* Flex column + maxHeight: the grid ends after its last row on tall
            screens and scrolls inside the viewport on short ones. */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            maxHeight: 'calc(100vh - 100px)',
            width: '100%',
          }}
        >
          <DataGrid
            rows={rows}
            columns={columns}
            loading={ssidStatsQuery.isFetching}
            rowCount={rowCount}
            paginationMode="server"
            sortingMode="server"
            pageSizeOptions={[PAGE_SIZE]}
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            sortModel={sortModel}
            onSortModelChange={setSortModel}
            disableMultipleRowSelection
            // Hand cursor: clicking a row shows its locations on the map.
            sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
            rowSelectionModel={rowSelectionModel}
            onRowSelectionModelChange={(model) => {
              const [nextId] = [...model.ids];
              setSelectedRowId(nextId ?? null);
            }}
            disableColumnResize
            getRowClassName={(params) =>
              params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
            }
          />
        </Box>

        <Box>
          <Typography component="h3" variant="subtitle1" sx={{ mb: 0.5 }}>
            {t('ssidView.mapTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {mapHint}
          </Typography>
          <SsidGeoMap geo={selectedRow?.geo ?? null} />
        </Box>
      </Stack>
    </Box>
  );
}
