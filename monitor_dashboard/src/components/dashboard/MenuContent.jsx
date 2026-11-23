import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import {
  ExpandLess,
  ExpandMore,
  TapAndPlay,
  CellTower,
  Wifi,
} from '@mui/icons-material';
import { useState } from 'react';
import { Collapse, Divider } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { fetchTotalPerDeviceStats } from '../../statsApi/StatsApi';

const secondaryListItems = [
  { key: 'common.settings', icon: <SettingsRoundedIcon /> },
  { key: 'common.about', icon: <InfoRoundedIcon /> },
];

export default function MenuContent({ collapsed = false }) {
  const [openDevices, setOpenDevices] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const devicesQuery = useQuery({
    queryKey: ['total-per-device-stats'],
    queryFn: fetchTotalPerDeviceStats,
  });
  const devices = Object.keys(devicesQuery.data ?? {}).sort();
  const fadeSx = {
    opacity: collapsed ? 0 : 1,
    transition: 'opacity 150ms ease',
  };

  const menuSx = {
    flexGrow: 1,
    p: 1,
    justifyContent: 'space-between',
    '& .MuiList-root': { padding: 0, gap: '4px' },
    '& .MuiDivider-root': { mb: 0.5 },
    '& .MuiListItem-root .MuiListItemButton-root': {
      minHeight: 40,
      padding: '0 14px',
      gap: '12px',
      overflow: 'hidden',
    },
    '& .MuiListItem-root .MuiListItemIcon-root .MuiSvgIcon-root': {
      width: 20,
      height: 20,
    },
    '& .MuiListItemText-root': {
      minWidth: 0,
      overflow: 'hidden',
      whiteSpace: 'nowrap',
      ...fadeSx,
    },
    '& .MuiCollapse-root .MuiListItemText-root': {
      whiteSpace: 'normal',
      overflowWrap: 'anywhere',
    },
    '& .MuiListItemButton-root > .MuiSvgIcon-root': {
      flexShrink: 0,
      ...fadeSx,
    },
  };

  return (
    <Stack sx={menuSx}>
      <List dense>
        {/* Home */}
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/home'}
            onClick={() => navigate('/home')}
          >
            <ListItemIcon>
              <HomeRoundedIcon />
            </ListItemIcon>
            <ListItemText primary={t('common.home')} />
          </ListItemButton>
        </ListItem>

        {/* SSIDs */}
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/ssids'}
            onClick={() => navigate('/ssids')}
          >
            <ListItemIcon>
              <Wifi />
            </ListItemIcon>
            <ListItemText primary={t('common.ssids')} />
          </ListItemButton>
        </ListItem>

        {/* Devices (parent) */}
        <ListItem disablePadding>
          <ListItemButton onClick={() => setOpenDevices(!openDevices)}>
            <ListItemIcon>
              <CellTower />
            </ListItemIcon>
            <ListItemText primary={t('common.devices')} />
            {openDevices ? <ExpandLess /> : <ExpandMore />}
          </ListItemButton>
        </ListItem>

        {/* Devices (children) */}
        <Collapse in={!collapsed && openDevices} timeout="auto" unmountOnExit>
          <List component="div" dense disablePadding>
            {devices.map((device) => (
              <ListItem key={device} disablePadding sx={{ pl: 4 }}>
                <ListItemButton
                  selected={
                    decodeURIComponent(
                      location.pathname.split('/').pop() ?? '',
                    ) === device
                  }
                  onClick={() =>
                    navigate(`/device/${encodeURIComponent(device)}`)
                  }
                >
                  <ListItemIcon>
                    <TapAndPlay />
                  </ListItemIcon>
                  <ListItemText primary={device} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Collapse>
      </List>
      <List dense>
        <Divider />
        {secondaryListItems.map((item, index) => (
          <ListItem key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={t(item.key)} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}
