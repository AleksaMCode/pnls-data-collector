import Stack from '@mui/material/Stack';
import NavbarBreadcrumbs from './NavbarBreadcrumbs';
import ColorModeIconDropdown from '../../theme/ColorModeIconDropdown';
import { FormControlLabel, Switch, Tooltip, useTheme } from '@mui/material';
import { useLiveCount } from './LiveCountProvider';
import { toast } from 'react-toastify';

function isWorkingHours() {
  const now = new Date();

  const hour = Number(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Paris',
      hour: '2-digit',
      hour12: false,
    }).format(now),
  );

  return hour >= 7 && hour < 18;
}

export default function Header() {
  const { enabled, setEnabled } = useLiveCount();
  const theme = useTheme();

  const handleLiveToggle = (checked) => {
    setEnabled(checked);

    if (!isWorkingHours() && checked) {
      toast.error('Devices are offline', {
        toastId: 'devices-offline',
      });
      setTimeout(() => {
        setEnabled(false);
      }, 0);
    }
  };

  return (
    <Stack
      direction="row"
      sx={{
        display: { xs: 'none', md: 'flex' },
        width: '100%',
        alignItems: { xs: 'flex-start', md: 'center' },
        justifyContent: 'space-between',
        maxWidth: { sm: '100%', md: '1700px' },
        pt: 1.5,
      }}
      spacing={2}
    >
      <NavbarBreadcrumbs />
      <Stack direction="row" sx={{ gap: 1 }}>
        <Tooltip title="Toggle to view live Probe Request data">
          <FormControlLabel
            control={
              <Switch
                checked={enabled}
                disabled={!isWorkingHours()}
                onChange={(e, checked) => handleLiveToggle(checked)}
              />
            }
            label="Live View"
          />
        </Tooltip>
        <ColorModeIconDropdown />
      </Stack>
    </Stack>
  );
}
