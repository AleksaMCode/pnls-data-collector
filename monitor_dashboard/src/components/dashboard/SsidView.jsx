import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import FormControl from '@mui/material/FormControl';
import OutlinedInput from '@mui/material/OutlinedInput';
import InputAdornment from '@mui/material/InputAdornment';
import { DataGrid } from '@mui/x-data-grid';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import { useEffect, useMemo, useState } from 'react';
import { fetchSsidStats } from '../../statsApi/StatsApi';

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 400;

// Fields the API supports server-side sorting on.
const SERVER_SORTABLE_FIELDS = new Set([
  'ssid',
  'seen_count',
  'first_seen',
  'last_seen',
]);

function formatDateTime(value) {
  if (!value) {
    return '-';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString('en-GB', { timeZone: 'Europe/Paris' });
}

const columns = [
  {
    field: 'ssid',
    headerName: 'SSID',
    flex: 1.5,
    minWidth: 240,
    renderCell: (params) => params.row.ssid || '-',
  },
  {
    field: 'seen_count',
    headerName: 'Seen count',
    type: 'number',
    flex: 0.8,
    minWidth: 130,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => Number(params.row.seen_count ?? 0).toLocaleString(),
  },
  {
    field: 'first_seen',
    headerName: 'First seen',
    flex: 1,
    minWidth: 190,
    renderCell: (params) => formatDateTime(params.row.first_seen),
  },
  {
    field: 'last_seen',
    headerName: 'Last seen',
    flex: 1,
    minWidth: 190,
    renderCell: (params) => formatDateTime(params.row.last_seen),
  },
];

export default function SsidView() {
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

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        SSIDs
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        All captured SSIDs with how often and when they were seen. Use the
        search bar to filter by SSID name.
      </Typography>

      <Stack spacing={2}>
        <FormControl sx={{ width: '100%' }}>
          <OutlinedInput
            size="small"
            placeholder="Search SSID…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <SearchRoundedIcon fontSize="small" />
              </InputAdornment>
            }
          />
        </FormControl>

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
      </Stack>
    </Box>
  );
}
