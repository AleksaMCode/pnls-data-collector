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

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 400;

// Fields the API supports server-side sorting on.
const SERVER_SORTABLE_FIELDS = new Set([
  'ssid',
  'seen_count',
  'first_seen',
  'last_seen',
]);

function formatDateTime(value, locale) {
  if (!value) {
    return '-';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
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

  const [rows, setRows] = useState([]);
  const [rowCount, setRowCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isDownloadingCsv, setIsDownloadingCsv] = useState(false);

  const columns = useMemo(
    () => [
      {
        field: 'ssid',
        headerName: t('common.ssids'),
        flex: 1.5,
        minWidth: 240,
        renderCell: (params) => params.row.ssid || '-',
      },
      {
        field: 'seen_count',
        headerName: t('ssidView.seenCount'),
        type: 'number',
        flex: 0.8,
        minWidth: 130,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) =>
          Number(params.row.seen_count ?? 0).toLocaleString(),
      },
      {
        field: 'first_seen',
        headerName: t('ssidView.firstSeen'),
        flex: 1,
        minWidth: 190,
        renderCell: (params) => formatDateTime(params.row.first_seen, locale),
      },
      {
        field: 'last_seen',
        headerName: t('ssidView.lastSeen'),
        flex: 1,
        minWidth: 190,
        renderCell: (params) => formatDateTime(params.row.last_seen, locale),
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

  useEffect(() => {
    let isActive = true;

    async function loadSsids() {
      setIsLoading(true);
      try {
        const response = await fetchSsidStats({
          search: debouncedSearch || undefined,
          sortBy,
          sortOrder,
          offset: paginationModel.page * paginationModel.pageSize,
          limit: paginationModel.pageSize,
        });

        if (!isActive) {
          return;
        }

        const items = response.items ?? [];
        setRows(
          items.map((item, index) => ({
            id: `${item.ssid ?? 'ssid'}-${index}`,
            ssid: item.ssid,
            seen_count: item.seen_count,
            first_seen: item.first_seen,
            last_seen: item.last_seen,
          })),
        );
        setRowCount(response.pagination?.total ?? 0);
      } catch (err) {
        if (isActive) {
          console.error('Failed to fetch SSID stats:', err);
          setRows([]);
          setRowCount(0);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    loadSsids();

    return () => {
      isActive = false;
    };
  }, [debouncedSearch, sortBy, sortOrder, paginationModel]);

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
        <Box sx={{ height: 'calc(100vh - 100px)', width: '100%' }}>
          <DataGrid
            rows={rows}
            columns={columns}
            loading={isLoading}
            rowCount={rowCount}
            paginationMode="server"
            sortingMode="server"
            pageSizeOptions={[PAGE_SIZE]}
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            sortModel={sortModel}
            onSortModelChange={setSortModel}
            disableRowSelectionOnClick
            disableColumnResize
            getRowClassName={(params) =>
              params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
            }
          />
        </Box>
      </Stack>
    </Box>
  );
}
