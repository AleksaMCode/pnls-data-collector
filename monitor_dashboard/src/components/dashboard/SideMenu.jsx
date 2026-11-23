import { styled } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import MuiDrawer, { drawerClasses } from '@mui/material/Drawer';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import MenuContent from './MenuContent';
import OptionsMenu from './OptionsMenu';
import { useAuth } from '../../context/authContext';
import PnlsCard from './PnlsCard';
import { useTranslation } from 'react-i18next';
import { useEffect, useState } from 'react';

const drawerWidth = 250;
const collapsedDrawerWidth = 65;
const transitionMs = 200;
const toggleButtonWidth = 48;
// Width of the logo card when the menu is open: drawer minus its border,
// the header padding (2 x 12), the gap (8) and the toggle button. Keeping it
// fixed stops the card from reflowing while the panel animates.
const headerCardWidth = drawerWidth - 1 - 24 - 8 - toggleButtonWidth;

function getDisplayNameFromEmail(email) {
  if (!email) {
    return 'User';
  }

  let username = email.split('@')[0];
  username = username.split('+')[0];

  const parts = username.split(/[.-]/);

  const capitalized = parts.map(
    (part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase(),
  );

  if (capitalized.length === 1) {
    return capitalized[0];
  }
  // TODO Update this logic - this isn't the best as email can have multiple dots or minutes. #techdept
  return `${capitalized[0]} ${capitalized[1]}`;
}

const Drawer = styled(MuiDrawer, {
  shouldForwardProp: (prop) => prop !== 'open' && prop !== 'layoutOpen',
})(({ open, layoutOpen }) => ({
  // The root is the slot the page content flows around. It follows
  // `layoutOpen`, which trails `open` until the panel animation is done.
  width: layoutOpen ? drawerWidth : collapsedDrawerWidth,
  flexShrink: 0,
  boxSizing: 'border-box',
  mt: 10,
  [`& .${drawerClasses.paper}`]: {
    width: open ? drawerWidth : collapsedDrawerWidth,
    boxSizing: 'border-box',
    overflowX: 'hidden',
    transition: `width ${transitionMs}ms ease`,
  },
}));

export default function SideMenu({ open, onToggle }) {
  const { currentUser } = useAuth();
  const { t } = useTranslation();
  const displayName = getDisplayNameFromEmail(currentUser?.email);

  const [layoutOpen, setLayoutOpen] = useState(open);
  useEffect(() => {
    const timeoutId = setTimeout(() => setLayoutOpen(open), transitionMs);
    return () => clearTimeout(timeoutId);
  }, [open]);

  const fadeSx = {
    opacity: open ? 1 : 0,
    transition: 'opacity 150ms ease',
  };

  return (
    <Drawer
      variant="permanent"
      open={open}
      layoutOpen={layoutOpen}
      sx={{
        display: { xs: 'none', md: 'block' },
        [`& .${drawerClasses.paper}`]: {
          backgroundColor: 'background.paper',
        },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          mt: 'calc(var(--template-frame-height, 0px) + 4px)',
          py: 1.5,
          px: open ? 1.5 : 1,
          gap: open ? 1 : 0,
          transition: `padding ${transitionMs}ms ease, gap ${transitionMs}ms ease`,
        }}
      >
        <Box
          aria-hidden={!open}
          sx={{ flex: 1, minWidth: 0, overflow: 'hidden', ...fadeSx }}
        >
          <Box sx={{ width: headerCardWidth }}>
            <PnlsCard
              primary="PNLS-DC"
              secondary={t('menu.monitoringDashboard')}
              color="primary.main"
              icon={
                <Box
                  component="img"
                  src="https://raw.githubusercontent.com/AleksaMCode/Preferred-Network-List-Sniffer/refs/heads/main/resources/rpis_logo.png"
                  alt="PNLS logo"
                  sx={{ width: 24, height: 24, objectFit: 'contain' }}
                />
              }
            />
          </Box>
        </Box>
        <IconButton
          size="small"
          onClick={onToggle}
          aria-label="toggle sidebar"
          sx={{
            flexShrink: 0,
            height: 76,
            width: toggleButtonWidth,
            borderRadius: 3,
            border: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          {open ? <ChevronLeft /> : <ChevronRight />}
        </IconButton>
      </Box>
      <Divider />
      <Box
        sx={{
          overflow: 'auto',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <MenuContent collapsed={!open} />
      </Box>
      <Stack
        direction="row"
        sx={{
          py: 2,
          // 14px keeps the 36px avatar centred in the collapsed rail.
          px: open ? 2 : 1.75,
          gap: 1,
          alignItems: 'center',
          borderTop: '1px solid',
          borderColor: 'divider',
          overflow: 'hidden',
          transition: `padding ${transitionMs}ms ease`,
        }}
      >
        <Avatar
          sizes="small"
          alt={displayName}
          src="/static/images/avatar/7.jpg"
          sx={{ width: 36, height: 36, flexShrink: 0 }}
        />
        <Box aria-hidden={!open} sx={{ flex: 1, minWidth: 0, ...fadeSx }}>
          <Typography
            noWrap
            variant="body2"
            sx={{ fontWeight: 500, lineHeight: '16px' }}
          >
            {displayName}
          </Typography>
          <Typography
            noWrap
            component="div"
            variant="caption"
            sx={{ color: 'text.secondary' }}
          >
            {currentUser?.email}
          </Typography>
        </Box>
        {open && <OptionsMenu />}
      </Stack>
    </Drawer>
  );
}
