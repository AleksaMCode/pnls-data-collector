import { styled } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import MuiDrawer, { drawerClasses } from '@mui/material/Drawer';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import MenuContent from './MenuContent';
import OptionsMenu from './OptionsMenu';
import { useAuth } from '../../context/authContext';
import PnlsCard from './PnlsCard';
import { useTranslation } from 'react-i18next';

const drawerWidth = 250;

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

const Drawer = styled(MuiDrawer)({
  width: drawerWidth,
  flexShrink: 0,
  boxSizing: 'border-box',
  mt: 10,
  [`& .${drawerClasses.paper}`]: {
    width: drawerWidth,
    boxSizing: 'border-box',
  },
});

export default function SideMenu() {
  const { currentUser } = useAuth();
  const { t } = useTranslation();
  const displayName = getDisplayNameFromEmail(currentUser?.email);

  return (
    <Drawer
      variant="permanent"
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
          mt: 'calc(var(--template-frame-height, 0px) + 4px)',
          p: 1.5,
        }}
      >
        <PnlsCard
          primary="PNLS-DC"
          secondary={t('menu.monitoringDashboard')}
          color="primary.main"
        />
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
        <MenuContent />
      </Box>
      <Stack
        direction="row"
        sx={{
          p: 2,
          gap: 1,
          alignItems: 'center',
          borderTop: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Avatar
          sizes="small"
          alt={displayName}
          src="/static/images/avatar/7.jpg"
          sx={{ width: 36, height: 36 }}
        />
        <Box sx={{ mr: 'auto' }}>
          <Typography
            variant="body2"
            sx={{ fontWeight: 500, lineHeight: '16px' }}
          >
            {displayName}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {currentUser?.email}
          </Typography>
        </Box>
        <OptionsMenu />
      </Stack>
    </Drawer>
  );
}
