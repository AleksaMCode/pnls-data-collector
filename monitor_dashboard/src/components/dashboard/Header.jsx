import Stack from '@mui/material/Stack';
import NavbarBreadcrumbs from './NavbarBreadcrumbs';
import ColorModeIconDropdown from '../../theme/ColorModeIconDropdown';
import LanguageIconDropdown from '../../theme/LanguageIconDropdown';
import { FormControlLabel, Switch, Tooltip } from '@mui/material';
import { useLiveCount } from './LiveCountProvider';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

/**
 * @deprecated At the moment there is no need to use this helper function as devices are always live.
 */
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
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const hideLiveToggle = pathname === '/ssids';

  const handleLiveToggle = (checked) => {
    setEnabled(checked);

    // if (!isWorkingHours() && checked) {
    //   toast.error('Devices are offline', {
    //     toastId: 'devices-offline',
    //   });
    //   setTimeout(() => {
    //     setEnabled(false);
    //   }, 0);
    // }
  };

  return (
    <Stack
      direction="row"
      sx={{
        display: { xs: 'none', md: 'flex' },
        width: '100%',
        alignItems: { xs: 'flex-start', md: 'center' },
        justifyContent: 'space-between',
        pt: 1.5,
      }}
      spacing={2}
    >
      <NavbarBreadcrumbs />
      <Stack direction="row" sx={{ gap: 1 }}>
        {!hideLiveToggle && (
          <Tooltip title={t('header.toggleLiveTooltip')}>
            <FormControlLabel
              control={
                <Switch
                  checked={enabled}
                  // disabled={!isWorkingHours()}
                  onChange={(e, checked) => handleLiveToggle(checked)}
                />
              }
              label={t('common.liveView')}
            />
          </Tooltip>
        )}
        <LanguageIconDropdown />
        <ColorModeIconDropdown />
      </Stack>
    </Stack>
  );
}
