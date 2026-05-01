import { DataGrid } from '@mui/x-data-grid';

const columns = [
  {
    field: 'company',
    headerName: 'Company',
    flex: 1.5,
    minWidth: 240,
  },
  {
    field: 'country',
    headerName: 'Country (alpha3)',
    flex: 1,
    minWidth: 150,
    renderCell: (params) => params.row.country || '-',
  },
  {
    field: 'count',
    headerName: 'Count',
    type: 'number',
    flex: 0.8,
    minWidth: 120,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => Number(params.row.count ?? 0).toLocaleString(),
  },
  {
    field: 'percentage',
    headerName: 'Percentage',
    type: 'number',
    flex: 0.8,
    minWidth: 130,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => `${Number(params.row.percentage ?? 0).toFixed(4)}%`,
  },
];

export default function ManufacturerDataGrid({ manufacturers = [] }) {
  const rows = manufacturers.map((manufacturer, index) => ({
    id: `${manufacturer.company}-${manufacturer.country ?? 'NA'}-${index}`,
    company: manufacturer.company ?? '-',
    country: manufacturer.country ?? null,
    count: Number(manufacturer.count ?? 0),
    percentage: Number(manufacturer.percentage ?? 0),
  }));

  return (
    <DataGrid
      rows={rows}
      columns={columns}
      disableRowSelectionOnClick
      initialState={{
        pagination: { paginationModel: { pageSize: 5 } },
      }}
      pageSizeOptions={[5, 10, 20]}
      getRowClassName={(params) =>
        params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
      }
      sx={{
        '& .MuiDataGrid-row': {
          backgroundColor: 'common.white',
        },
        '& .MuiDataGrid-row:hover': {
          backgroundColor: 'primary.50',
        },
      }}
    />
  );
}
